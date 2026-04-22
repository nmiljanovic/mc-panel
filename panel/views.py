import os
import json
from django import forms
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .utils import (
    get_server_stats,
    read_properties,
    save_properties,
    is_server_running,
    start_bedrock_server,
    stop_bedrock_server,
    get_latest_logs,
    handle_world_upload,
    delete_world_dir,
    update_bedrock_server,
    get_json_data,
    save_json_data,
    live_world_backup,
    restore_world,
    player_access_control
)


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Player Name",
        widget=forms.TextInput(attrs={
            'style': (
                'width: 100%; box-sizing: border-box; '
                'padding: 12px; margin-bottom: 10px;'
            ),
            'placeholder': '••••••••••••••'
        })
    )
    password = forms.CharField(
        label="Access Key",
        widget=forms.PasswordInput(attrs={
            'style': (
                'width: 100%; box-sizing: border-box; '
                'padding: 12px; margin-bottom: 10px;'
            ),
            'placeholder': '••••••••••••••'
        })
    )


@login_required
def dashboard(request):
    server_path = settings.SERVER_PATH
    pipe_path = settings.PIPE_PATH
    log_file = os.path.join(server_path, settings.LOG_FILE)
    wiki_url = settings.WIKI_URL
    stats = get_server_stats()
    process_name = 'bedrock_server'

    if request.method == "POST":
        if 'start' in request.POST.get("action"):
            success, message = start_bedrock_server(server_path, pipe_path)
            if not success:
                messages.error(request, f"{message}")

        elif 'stop' in request.POST.get("action"):
            success, message = stop_bedrock_server(process_name)
            if not success:
                messages.error(request, f"{message}")

        elif 'update' in request.POST.get("action"):
            success, message = update_bedrock_server(server_path, wiki_url)
            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        return redirect('dashboard')

    running_status = is_server_running()

    return render(request, 'dashboard.html', {
        'stats': stats,
        'is_running': running_status,
        'logs': get_latest_logs(os.path.join(server_path, f"{log_file}"))
    })


@login_required
def manage_settings(request):
    server_path = settings.SERVER_PATH
    prop_path = os.path.join(server_path, 'server.properties')
    if request.method == "POST":
        # Get all updated keys from the form
        new_settings = {
            key: value for key, value in request.POST.items()
            if key != 'csrfmiddlewaretoken'
        }
        success, message = save_properties(prop_path, new_settings)
        if success:
            messages.success(request, f"{message}")
        else:
            messages.error(request, f"{message}")

    success, message, current_settings = read_properties(prop_path)
    if not success:
        messages.error(request, f"{message}")

    return render(request, 'settings.html', {'settings': current_settings})


@login_required
def manage_assets(request):
    server_path = settings.SERVER_PATH
    worlds_path = os.path.join(server_path, 'worlds')
    pipe_path = settings.PIPE_PATH
    world_backup_path = settings.WORLD_BACKUP_PATH

    # Current active world
    active_world = read_properties(
        os.path.join(server_path, 'server.properties'))[2].get('level-name')

    # List existing worlds for the "Load World" dropdown
    worlds = ["No worlds found. Start the server first."]
    if os.path.exists(worlds_path):
        worlds = [
            d for d in os.listdir(worlds_path)
            if os.path.isdir(os.path.join(worlds_path, d))
        ]

    # List existing world backups for the "Restore World" dropdown
    world_backups = ["No world backups directory found."]
    if os.path.exists(world_backup_path):
        world_backups = [
            f for f in os.listdir(world_backup_path)
            if f.lower().endswith('.zip') and
            os.path.isfile(os.path.join(world_backup_path, f))
        ]

    if request.method == "POST":
        if 'set_world' in request.POST:
            selected_world = request.POST.get('world_name')
            # Use save_properties to update level-name
            success, message = save_properties(
                os.path.join(server_path, 'server.properties'),
                {'level-name': selected_world}
            )
            # Django message framework
            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        elif 'delete_world' in request.POST:
            selected_world = request.POST.get('world_name')
            world_del_path = os.path.join(
                server_path, 'worlds', selected_world)
            success, message = delete_world_dir(
                world_del_path, selected_world, active_world
            )

            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        elif 'backup_world' in request.POST:
            selected_world = request.POST.get('world_name')
            world_path = os.path.join(
                server_path, 'worlds', selected_world)
            success, message = live_world_backup(
                server_path, pipe_path, selected_world, world_path
            )

            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        elif 'restore_world' in request.POST:
            selected_world = request.POST.get('world_backup_file')
            success, message = restore_world(
                selected_world, worlds_path, world_backup_path
            )

            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        elif 'upload_world' in request.POST:
            world_file = request.FILES['world_file']
            success, message = handle_world_upload(
                server_path, worlds_path, world_file
            )
            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        return redirect('manage_assets')

    return render(request, 'assets.html', {
        'worlds': worlds,
        'active_world': active_world,
        'world_backups': world_backups
    })


@login_required
def manage_access(request):
    server_path = settings.SERVER_PATH
    log_file = os.path.join(server_path, settings.LOG_FILE)
    pipe_path = settings.PIPE_PATH
    allowlist_file = os.path.join(server_path, 'allowlist.json')
    permissions_file = os.path.join(server_path, 'permissions.json')

    if request.method == "POST" and request.POST.get("action") == 'submit':
        # Get the raw string from the textarea
        allowlist_raw = request.POST.get('allowlist_data')
        permissions_raw = request.POST.get('permissions_data')

        # Validate and save Allowlist, Permissions
        success, message = save_json_data(allowlist_file, allowlist_raw)

        if success:
            messages.success(request, f"{message} allowlist.json file.")
        else:
            messages.error(request, f"{message} - allowlist.json")

        success, message = save_json_data(permissions_file, permissions_raw)

        if success:
            messages.success(request, f"{message} permissions.json file.")
        else:
            messages.error(request, f"{message} - permissions.json")

        return redirect('manage_access')

    # Player access control (add,remove,op,deop,reload)
    elif request.method == "POST":
        player_name = request.POST.get("player_name")
        action = request.POST.get("action")

        if action == "reload":
            command = "allowlist reload"
        elif action == "add" or action == "remove":
            command = f'allowlist {action} "{player_name}"'
        elif action == "op" or action == "deop":
            command = f'{action} "{player_name}"'

        success, message = player_access_control(command, pipe_path, log_file)
        if success:
            messages.success(request, "Player access successfully updated.")
        if not success:
            messages.error(
                request, f"Unable to update player access: {message}")

        return redirect('manage_access')

    # GET request: Load current JSON data
    success, message, allowlist_data = get_json_data(allowlist_file)
    if not success:
        messages.error(request, f"{message} - allowlist.json")

    success, message, permissions_data = get_json_data(permissions_file)
    if not success:
        messages.error(request, f"{message} - permissions.json")

    context = {
        'allowlist': json.dumps(allowlist_data, indent=4),
        'permissions': json.dumps(permissions_data, indent=4),
    }
    return render(request, 'access.html', context)
