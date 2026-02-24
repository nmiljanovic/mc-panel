#!/usr/bin/bash

# Configuration
MC_DIR="minecraft/bedrock"
SERVICE_NAME="${USER}-mcpanel.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
WORK_DIR="/home/${USER}/mc_panel"
WIKI_URL="https://minecraft.wiki/w/Bedrock_Dedicated_Server"

echo 
echo "Inital Configuration for Django Bedrock Panel"
echo
echo "Running uv sync..."
uv sync --no-dev
echo
echo "Checking for minecraft/bedrock directory..."

# 1. Check for minecraft directory
if [ ! -d "$MC_DIR" ]; then
    read -p "Directory '$MC_DIR' not found. Download and unzip latest Bedrock server? (y/n): " confirm
    mkdir -p $MC_DIR
    if [[ $confirm == [yY] ]]; then
	DOWNLOAD_URL=$(curl -s -L -A "Mozilla/5.0" "$WIKI_URL" | \
   	grep -oP 'https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-[0-9.]+\.zip' | \
     	grep -v "preview" | tail -n 1)
        
	if [ -z "$DOWNLOAD_URL" ]; then
            echo "Error: Could not find download link."
            exit 1
        fi
	
	echo "Downloading: $DOWNLOAD_URL"
	wget -q --show-progress --content-disposition "$DOWNLOAD_URL"

        # Identify the downloaded zip (since the version number changes)
        ZIP_FILE=$(ls bedrock-server-*.zip | tail -n 1)
        
        if [ -f "$ZIP_FILE" ]; then
            unzip "$ZIP_FILE" -d "$MC_DIR"
            rm "$ZIP_FILE"
            echo "Minecraft server unzipped from $ZIP_FILE into $MC_DIR."
        else
            echo "Error: Zip file not found after download."
            exit 1
        fi
    else
        echo "Download cancelled. Exiting."
        exit 1
    fi
    else
	echo "Server directory already exists."
fi

# 2. Check and Create Systemd Service
echo
echo "Checking for Systemd service..."

if [ ! -f "$SERVICE_PATH" ]; then
    echo "Service $SERVICE_NAME not found. Creating it..."

    # Write the service file (requires sudo)
    cat <<EOF | sudo tee $SERVICE_PATH > /dev/null
[Unit]
Description=Django Bedrock Panel
After=network.target

[Service]
User=${USER}
Group=${USER}
WorkingDirectory=$WORK_DIR
ExecStart=/home/${USER}/.local/bin/uv run gunicorn manager.wsgi:application --bind 127.0.0.1:50222
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    echo "Reloading systemd and enabling service..."
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    echo "Service $SERVICE_NAME created and enabled."

else
    echo "Service $SERVICE_NAME already exists."
fi

echo
echo "Finished." 
