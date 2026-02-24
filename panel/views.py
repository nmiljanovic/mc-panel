import os
import subprocess
from django import forms
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .utils import (
    get_server_stats,
    read_properties,
    save_properties,
    is_server_running,
    stop_bedrock_server,
    get_latest_logs,
    handle_world_upload,
    delete_world_dir
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
    stats = get_server_stats()
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start":
            if not is_server_running():
                # Your existing Popen start logic here
                subprocess.Popen(
                    './bedrock_server > server_output.log 2>&1',
                    cwd='minecraft/bedrock/',
                    shell=True
                )

        elif action == "stop":
            stop_bedrock_server()

        return redirect('dashboard')

    # Use the check function instead of the global variable
    running_status = is_server_running()

    return render(request, 'dashboard.html', {
        'stats': stats,
        'is_running': running_status,
        'logs': get_latest_logs('minecraft/bedrock/server_output.log')
    })


@login_required
def edit_settings(request):
    prop_path = 'minecraft/bedrock/server.properties'
    if request.method == "POST":
        # Get all updated keys from the form
        new_settings = {
            key: value for key, value in request.POST.items()
            if key != 'csrfmiddlewaretoken'
            }
        save_properties(prop_path, new_settings)
        return redirect('dashboard')

    current_settings = read_properties(prop_path)
    return render(request, 'settings.html', {'settings': current_settings})


@login_required
def manage_assets(request):
    server_path = 'minecraft/bedrock/'
    worlds_path = os.path.join(server_path, 'worlds')

    # Current active world
    active_world = read_properties(
            os.path.join(server_path, 'server.properties')).get('level-name')

    # List existing worlds for the "Load World" dropdown
    worlds = ["No worlds found. Start the server first."]
    if os.path.exists(worlds_path):
        worlds = [
            d for d in os.listdir(worlds_path)
            if os.path.isdir(os.path.join(worlds_path, d))
        ]

    if request.method == "POST":
        if 'upload_world' in request.POST:
            world_file = request.FILES['world_file']
            success, message = handle_world_upload(
                    server_path, worlds_path, world_file
                    )
            # Add message to Django messages framework
            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        elif 'set_world' in request.POST:
            selected_world = request.POST.get('world_name')
            # Use save_properties to update level-name
            success, message = save_properties(
                os.path.join(server_path, 'server.properties'),
                {'level-name': selected_world}
            )
            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        elif 'delete_world' in request.POST:
            selected_world = request.POST.get('world_name')
            world_del_path = os.path.join(server_path, 'worlds', selected_world)
            success, message = delete_world_dir(
                    world_del_path, selected_world, active_world
                    )

            if success:
                messages.success(request, f"{message}")
            else:
                messages.error(request, f"{message}")

        return redirect('manage_assets')

    return render(request, 'assets.html', {
        'worlds': worlds, 'active_world': active_world
    })
