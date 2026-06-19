import os
import re
import sys
import json
import time
import psutil
import shutil
import zipfile
import subprocess
import urllib.request
from django.conf import settings
from mcstatus import BedrockServer
from .models import OnlinePlayer


def get_server_stats(ip="127.0.0.1", port=19132):
    # System Stats
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    stats = {
        'cpu_pct': psutil.cpu_percent(interval=1),
        'disk_pct': psutil.disk_usage('/').percent,
        'memory_pct': psutil.virtual_memory().percent,
        'memory_used': round(memory.used / (1024**3), 2),
        'memory_total': round(memory.total / (1024**3), 2),
        'disk_used': round(disk.used / (1024**3), 1),
        'disk_total': round(disk.total / (1024**3), 1),
        # Satus page
        "online": False,
        "motd": "N/A",
        "players_online": 0,
        "players_max": 0,
        "version": "N/A",
        "map_name": "N/A",
        "gamemode": "N/A",
        "latency": 0,
        "players": []
    }

    # Minecraft Stats
    server_path = settings.SERVER_PATH
    properties_path = os.path.join(server_path, "server.properties")
    current_port = get_port_from_properties(properties_path)

    try:
        server = BedrockServer.lookup(f"{ip}:{current_port}")
        status = server.status()
        stats['online'] = True
        stats['motd'] = status.motd.to_plain()
        stats['players_online'] = status.players.online
        stats['players_max'] = status.players.max
        stats['version'] = status.version.version
        stats['map_name'] = status.map_name
        stats['gamemode'] = status.gamemode
        stats['latency'] = round(status.latency, 2)
        stats['players'] = OnlinePlayer.objects.all()

    except Exception as e:
        stats['online'] = False
        print(f"Error: {str(e)}")

    return stats


def read_properties(file_path):
    config = {}
    # Read server.properties file
    if not os.path.exists(file_path):
        return False, "No server.properties file found.", {}

    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
        return True, "", config

    except PermissionError:
        return False, "Permission denied. Check file permissions.", {}
    except OSError as e:
        return False, f"File system error: {str(e)}", {}
    except Exception as e:
        return False, f"Unable to read server.properties file: {str(e)}", {}


def save_properties(file_path, new_config):
    if not os.path.exists(file_path):
        return False, "No server.properties file found."

    if is_server_running():
        return False, "Stop the server first."

    lines = []
    # Read existing lines to preserve comments
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if line.startswith('#') or '=' not in line:
                    lines.append(line)
                    continue
                key = line.split('=', 1)[0].strip()
                if key in new_config:
                    lines.append(f"{key}={new_config[key]}\n")
                else:
                    lines.append(line)

        with open(file_path, 'w') as f:
            f.writelines(lines)
        return True, "Successfully updated server.properties file."

    except PermissionError:
        return False, "Permission denied. Check file permissions."
    except OSError as e:
        return False, f"File system error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_latest_logs(log_file, line_count=30):
    if not os.path.exists(log_file):
        return "No log file found. Start the server first."

    try:
        with open(log_file, 'r') as f:
            # Get the last N lines efficiently
            lines = f.readlines()
            return "".join(lines[-line_count:])

    except PermissionError:
        return "Permission denied. Check file permissions."
    except OSError as e:
        return f"File system error: {str(e)}"
    except Exception as e:
        return f"Unable to read log file: {str(e)}"


def start_bedrock_server(server_path, pipe_path, log_file, scraper_path):
    if is_server_running():
        return False, "Server is already started."

    # Check if pipe exists before starting the process
    if not os.path.exists(pipe_path):
        try:
            os.mkfifo(pipe_path)

        except PermissionError:
            return False, "Permission denied. Check file permissions."
        except OSError as e:
            return False, f"Unable to create stdin pipe: {str(e)}"
        except Exception as e:
            return False, f"Unable to start the server: {str(e)}"

    try:
        # Stdin pipe for sending commands to live server
        subprocess.Popen(
            f"tail -f {pipe_path} | ./bedrock_server > {log_file} 2>&1",
            cwd=server_path,
            shell=True
        )
        # Start the log scraper subprocess
        subprocess.Popen(
            [sys.executable, scraper_path],
            env=os.environ.copy()  # Pass current Django environment variables
        )
        return True, "Server and scraper successfully started."

    except Exception as e:
        return False, f"Unable to start the server: {str(e)}"


def stop_bedrock_server(process_name, scraper_path, pipe_path):
    if not is_server_running():
        return False, "Server is already stoppped."

    targets = [process_name, scraper_path, pipe_path]
    stopped_process = False
    # Look for the process by name
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            # Check the process name OR the command line (for python scripts)
            cmdline = " ".join(proc.info['cmdline'] or [])
            if any(target in proc.info['name'] or target in cmdline for target in targets):
                proc.terminate()
                stopped_process = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        except Exception as e:
            return False, f"Unable to stop the server: {str(e)}"

    OnlinePlayer.objects.all().delete()

    if stopped_process:
        return True, "Server and scraper successfully stopped."
    else:
        return False, "No running processes were found."


def is_server_running():
    for proc in psutil.process_iter(['name']):
        if 'bedrock_server' in proc.info['name']:
            return True
    return False


def get_port_from_properties(file_path):
    default_port = 19132
    if not os.path.exists(file_path):
        return default_port

    try:
        with open(file_path, 'r') as f:
            for line in f:
                # Remove spaces and look for the port key
                clean_line = line.strip().replace(" ", "")
                if clean_line.startswith("server-port="):
                    return int(clean_line.split("=")[1])
    except Exception:
        pass  # Fallback to default if there is a read error

    return default_port


def handle_world_upload(server_path, worlds_path, world_file):
    # Setup paths
    os.makedirs(worlds_path, exist_ok=True)

    # Use the filename (minus .mcworld) as the folder name
    world_name = os.path.splitext(world_file.name)[0]
    final_dest = os.path.join(worlds_path, world_name)

    # Save temporary file
    temp_path = os.path.join(server_path, 'temp', world_file.name)
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)

    try:
        with open(temp_path, 'wb+') as f:
            for chunk in world_file.chunks():
                f.write(chunk)

        # Extract logic
        with zipfile.ZipFile(temp_path, 'r') as zip_ref:
            # Look for levelname.txt to find the true world root
            level_info = next(
                (i for i in zip_ref.infolist()
                 if i.filename.endswith('levelname.txt')),
                None
            )

            # If no levelname.txt, it's likely not a valid world
            if not level_info:
                return False, "Not a valid .mcworld (missing levelname.txt)"

            internal_root = os.path.dirname(level_info.filename)

            # Flatten and extract
            for member in zip_ref.infolist():
                if not member.filename.startswith(internal_root):
                    continue

                # Calculate relative path
                rel_p = os.path.relpath(member.filename, internal_root)
                target_p = os.path.normpath(os.path.join(final_dest, rel_p))

                if member.is_dir():
                    os.makedirs(target_p, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_p), exist_ok=True)
                    with zip_ref.open(member) as source, \
                            open(target_p, "wb") as target:
                        shutil.copyfileobj(source, target)

        return True, "World successfully imported."

    except Exception as e:
        return False, f"Unable to import world: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def delete_world_dir(world_del_path, selected_world, active_world):
    if is_server_running():
        return False, "Cannot delete world. Stop the server first."
    if not os.path.exists(world_del_path):
        return False, "World directory does not exist."
    if selected_world in active_world:
        return False, "Cannot delete active world."

    try:
        shutil.rmtree(world_del_path)
        return True, "World successfully deleted."

    except PermissionError:
        return False, "Permission denied. Stop the server first."
    except OSError as e:
        return False, f"File system error: {str(e)}"
    except Exception as e:
        return False, f"Unable to delete world: {str(e)}"


def get_latest_version_url(wiki_url):
    try:
        # Get the HTML
        req = urllib.request.Request(
            wiki_url, headers={"User-Agent": "Wget/1.21"})
        with urllib.request.urlopen(req, timeout=10) as response:
            # urllib returns bytes, decode to string
            html_content = response.read().decode('utf-8')

        # Look for https link containing 'bin-linux' ending in .zip
        links = re.findall(
            r'https://[^\s"<>]+bin-linux[^\s"<>]+?\.zip', html_content)

        # Filter out "preview" versions
        stable_link = [link for link in links if "preview" not in link.lower()]

        # Return the last match
        return stable_link[-1] if stable_link else None

    except Exception as e:
        return False, f"Unable to fetch url from wiki: {str(e)}"
        return None


def compare_server_versions(wiki_url):
    match = re.search(
        r'bedrock-server-([\d.]+)\.zip', get_latest_version_url(wiki_url))
    if not match:
        return False, "Unable to parse version url from wiki."

    # Conc ver to 3 decimal places (mcstatus format 0.0.0)
    latest_version_str = ".".join(match.group(1).split(".")[:3])
    current_version_str = get_server_stats().get('version', '0.0.0')

    # Map conversion e.g., 1.26.23.1 to (1, 26, 23, 1)
    latest_version_tuple = tuple(map(int, latest_version_str.split('.')))
    current_version_tuple = tuple(map(int, current_version_str.split('.')))
    if latest_version_tuple > current_version_tuple:
        return True, f"Bedrock server v{latest_version_str} is available."
    return False, "Server is up to date."


def update_bedrock_server(server_path, wiki_url):
    if is_server_running():
        return False, "Cannot update. Stop the server first."

    download_url = get_latest_version_url(wiki_url)
    if not download_url:
        return False, "Unable to find download URL."

    # Setup temp path
    temp_path = os.path.join(server_path, 'temp')
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)
    os.makedirs(temp_path)

    # Download via wget
    try:
        subprocess.run([
            'wget', '-q', '-P', temp_path, download_url
        ], check=True, timeout=90)
    except subprocess.TimeoutExpired:
        return False, "Download timed out."
    except subprocess.CalledProcessError:
        return False, "Unable to download the file."

    server_zip = os.path.join(temp_path, os.path.basename(download_url))

    # Extract
    with zipfile.ZipFile(server_zip, 'r') as zip_ref:
        zip_ref.extractall(temp_path)

    # Define items to PRESERVE (Worlds, Configs, Mods)
    preserve = [
        'worlds',
        'server.properties',
        'allowlist.json',
        'permissions.json',
        'resource_packs',
        'behavior_packs'
    ]

    # Atomic Update: Move files from Temp to Server Path
    for item in os.listdir(temp_path):
        if item in preserve or item.endswith('.zip'):
            continue

        src = os.path.join(temp_path, item)
        dst = os.path.join(server_path, item)

        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Make bedrock_server file executable
    binary_path = os.path.join(server_path, 'bedrock_server')
    if os.path.exists(binary_path):
        os.chmod(binary_path, 0o755)

    shutil.rmtree(temp_path)
    return True, "Server successfully updated."


def get_json_data(file_path):
    if not os.path.exists(file_path):
        return False, "No file found", []

    try:
        with open(file_path, 'r') as f:
            json_data = json.load(f)
        return True, "", json_data

    except PermissionError:
        return False, "Permission denied. Check file permissions.", []
    except json.JSONDecodeError:
        return False, "File contains invalid JSON", []
    except OSError as e:
        return False, f"File system error: {str(e)}", []
    except Exception as e:
        return False, f"Unable to read JSON file: {str(e)}", []


def save_json_data(file_path, raw_json_string):
    try:
        # Parse the string into a Python object
        data = json.loads(raw_json_string)

        # Perform the write operation
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)

        return True, "Successfully updated"

    except PermissionError:
        return False, "Permission denied. Check file permissions."
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format: {str(e)}"
    except OSError as e:
        return False, f"File system error: {str(e)}"
    except Exception as e:
        return False, f"Unable to update JSON file: {str(e)}"


def live_world_backup(server_path, pipe_path, selected_world, world_path):
    if not is_server_running():
        return False, "Server is stopped. Start the server first."

    # World backup path
    backup_path = settings.WORLD_BACKUP_PATH
    if not os.path.exists(backup_path):
        os.makedirs(backup_path)

    try:
        # Inject 'save hold' into the pipe
        with open(pipe_path, "w") as pipe:
            pipe.write("save hold\n")
            pipe.flush()

        # Allow time for Bedrock to flush files to disk
        time.sleep(1)

        # Create the Zip file
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_file = os.path.join(
            backup_path, f"{selected_world}_{timestamp}.zip")
        # levelname_260419-102542 (world dir inside zip)
        world_dir_timestamp = f"{selected_world}_{timestamp}"

        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(world_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    # rel_path doesn't include full OS paths
                    # rel_path = os.path.relpath(
                    #    full_path, os.path.join(world_path, '..'))
                    rel_path = os.path.relpath(full_path, world_path)
                    set_path = os.path.join(world_dir_timestamp, rel_path)
                    zf.write(full_path, set_path)

        # Inject 'save resume'
        with open(pipe_path, "w") as pipe:
            pipe.write("save resume\n")
            pipe.flush()

        return True, "World successfully backed up."

    except Exception as e:
        # Emergency resume attempt
        try:
            with open(pipe_path, "w") as pipe:
                pipe.write("save resume\n")
        except OSError:
            pass

        return False, f"Unable to backup world: {str(e)}"


def restore_world(selected_world, worlds_path, world_backup_path):
    world_to_restore = os.path.join(world_backup_path, selected_world)

    try:
        with zipfile.ZipFile(world_to_restore, 'r') as zip_ref:
            zip_ref.extractall(worlds_path)
        return True, "World successfully restored. Change active."

    except OSError as e:
        return False, f"File system error: {str(e)}"
    except Exception as e:
        return False, f"Unable to restore world: {str(e)}"


def player_access_control(command, pipe_path, log_file):
    if not is_server_running():
        return False, "Server is stopped. Start the server first."

    try:
        # Send command to stdin pipe
        with open(pipe_path, 'w') as pipe:
            pipe.write(f"{command}\n")
            pipe.flush()

        time.sleep(1)

        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                if not lines:
                    return False, "Server log is empty."

                last_line = lines[-1].strip()

                # BDS output looks like: [2026-04-21 14:00:00:000 INFO]
                if "INFO" in last_line:
                    return True, f"{last_line}"
                elif "ERROR" in last_line:
                    return False, f"{last_line}"
        return False, f"Cannot find {log_file}"

    except OSError as e:
        return False, f"File system error: {str(e)}"
    except Exception as e:
        return False, f"Error sending command: {str(e)}"
