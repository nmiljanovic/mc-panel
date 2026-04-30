import os
import sys
import time
import django
from django.conf import settings

# Get the script directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Get the parent directory
project_root = os.path.abspath(os.path.join(script_dir, os.pardir))

if project_root not in sys.path:
    sys.path.append(project_root)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'panel.settings')
django.setup()

from panel.models import OnlinePlayer  # noqa


def watch_logs():
    server_path = settings.SERVER_PATH
    log_file = os.path.join(server_path, settings.LOG_FILE)

    # print("Watching BDS logs for player activity...")
    # Open the file and move to the end
    file = open(log_file, "r")
    file.seek(0, os.SEEK_END)

    while True:
        line = file.readline()
        if not line:
            time.sleep(1)
            continue

        # BDS Join Pattern: "Player connected: Name, xuid: ..."
        if "Player connected:" in line:
            name = line.split("Player connected: ")[1].split(",")[0].strip()
            OnlinePlayer.objects.get_or_create(username=name)
            # print(f"Detected Join: {name}")

        # BDS Leave Pattern: "Player disconnected: Name, xuid: ..."
        elif "Player disconnected:" in line:
            name = line.split("Player disconnected: ")[1].split(",")[0].strip()
            OnlinePlayer.objects.filter(username=name).delete()
            # print(f"Detected Leave: {name}")


if __name__ == "__main__":
    watch_logs()
