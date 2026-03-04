import os
import re
import psutil
import shutil
import zipfile
import subprocess
import urllib.request
from django.conf import settings
from mcstatus import BedrockServer


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
        'disk_total': round(disk.total / (1024**3), 1)
    }

    # Minecraft Stats
    server_path = settings.SERVER_PATH
    properties_path = os.path.join(server_path, "server.properties")
    current_port = get_port_from_properties(properties_path)

    try:
        server = BedrockServer.lookup(f"{ip}:{current_port}")
        status = server.status()
        stats['players_online'] = status.players.online
        stats['players_max'] = status.players.max
        stats['version'] = status.version.version
        stats['online'] = True
    except Exception as e:
        print(f"Ping failed: {str(e)}")
        stats['online'] = False

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
    except Exception as e:
        return False, f"Unable to read server.properties file: {str(e)}", {}


def save_properties(file_path, new_config):
    if not os.path.exists(file_path):
        return False, "No server.properties file found."

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
        return True, "Updated the server.properties file."
    except Exception as e:
        return False, f"Unable to update server.properties file: {str(e)}"


def get_latest_logs(log_file_path, line_count=30):
    if not os.path.exists(log_file_path):
        return "No logs found. Start the server first."

    with open(log_file_path, 'r') as f:
        # Get the last N lines efficiently
        lines = f.readlines()
        return "".join(lines[-line_count:])


def stop_bedrock_server():
    # Look for the process by name
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            if 'bedrock_server' in proc.info['name']:
                proc.terminate()  # Send the stop signal
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


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
    # 1. Setup paths
    os.makedirs(worlds_path, exist_ok=True)

    # Use the filename (minus .mcworld) as the folder name
    world_name = os.path.splitext(world_file.name)[0]
    final_dest = os.path.join(worlds_path, world_name)

    # 2. Save temporary file
    temp_path = os.path.join(server_path, 'temp', world_file.name)
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)

    try:
        with open(temp_path, 'wb+') as f:
            for chunk in world_file.chunks():
                f.write(chunk)

        # 3. Extract logic
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

            # 4. Flatten and extract
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

        return True, f"World '{world_name}' imported successfully."

    except Exception as e:
        return False, f"World import error: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def delete_world_dir(world_del_path, selected_world, active_world):
    # Delete world directory
    if is_server_running():
        return False, "Cannot delete world. Stop the server first."
    if selected_world in active_world:
        return False, "Cannot delete active world."
    if not os.path.exists(world_del_path):
        return False, "World directory does not exist."

    try:
        shutil.rmtree(world_del_path)
        return True, "World successfully deleted."
    except PermissionError:
        return False, "Permission denied. Is the server still running?"
    except Exception as e:
        return False, str(e)


def get_latest_version_url():
    WIKI_URL = "https://minecraft.wiki/w/Bedrock_Dedicated_Server"

    try:
        # 1. Fetch the HTML
        req = urllib.request.Request(
            WIKI_URL, headers={"User-Agent": "Wget/1.21"})
        with urllib.request.urlopen(req, timeout=10) as response:
            # urllib returns bytes, decode to string
            html_content = response.read().decode('utf-8')

        # Look for https link containing 'bin-linux' ending in .zip
        links = re.findall(
            r'https://[^\s"<>]+bin-linux[^\s"<>]+?\.zip', html_content)

        # 3. Filter out "preview" versions
        stable_link = [link for link in links if "preview" not in link.lower()]

        # 4. Return the last match
        return stable_link[-1] if stable_link else None

    except Exception as e:
        return False, f"Error fetching url from wiki: {str(e)}"
        return None


def update_bedrock_server(server_path):
    if is_server_running():
        return False, "Cannot update. Stop the server first."

    download_url = get_latest_version_url()
    if not download_url:
        return False, "Unable to find a valid download URL."

    # 1. Setup temp path
    temp_path = os.path.join(server_path, 'temp')
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)
    os.makedirs(temp_path)

    # 2. Download via wget
    try:
        subprocess.run([
            'wget', '-q', '-P', temp_path, download_url
        ], check=True, timeout=90)
    except subprocess.TimeoutExpired:
        return False, "Download timed out."
    except subprocess.CalledProcessError:
        return False, "Unable to download the file."

    server_zip = os.path.join(temp_path, os.path.basename(download_url))

    # 3. Extract
    with zipfile.ZipFile(server_zip, 'r') as zip_ref:
        zip_ref.extractall(temp_path)

    # 4. Define items to PRESERVE (Worlds, Configs, Mods)
    preserve = [
        'worlds',
        'server.properties',
        'allowlist.json',
        'permissions.json',
        'resource_packs',
        'behavior_packs'
    ]

    # 5. Atomic Update: Move files from Temp to Server Path
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

    # 6. Make bedrock_server file executable
    binary_path = os.path.join(server_path, 'bedrock_server')
    if os.path.exists(binary_path):
        os.chmod(binary_path, 0o755)

    shutil.rmtree(temp_path)
    return True, "Server updated successfully. All settings preserved."
