import os
import psutil
import shutil
import zipfile
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
        print(f"Ping failed: {e}")
        stats['online'] = False

    return stats


def read_properties(file_path):
    config = {}
    with open(file_path, 'r') as f:
        for line in f:
            if line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            config[key.strip()] = value.strip()
    return config


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
        return False, f"Error with server.properties file: {str(e)}"


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
        return False, "Shut down the server first."
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
