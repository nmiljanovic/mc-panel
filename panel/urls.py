from . import views
from .views import LoginForm
from django.urls import path
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.server_status, name='status'),
    path('manager/', views.manage_server, name='manage_server'),
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(
            template_name='login.html',
            authentication_form=LoginForm
        ),
        name='login'
    ),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api/latency/', views.player_latency_js, name='player_latency_js'),
    path('api/ping/', views.ping_endpoint, name='ping_endpoint'),
    path('settings/', views.manage_settings, name='manage_settings'),
    path('assets/', views.manage_assets, name='manage_assets'),
    path('access/', views.manage_access, name='manage_access')
]
