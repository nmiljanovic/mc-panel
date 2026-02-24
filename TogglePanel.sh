#!/usr/bin/bash

SERVICE="$USER-mcpanel.service"

if systemctl is-active --quiet "$SERVICE"; then
    echo "$SERVICE is running. Stopping it now..."
    sudo systemctl stop "$SERVICE"
else
    echo "$SERVICE is stopped. Starting it now..."
    sudo systemctl start "$SERVICE"
fi

