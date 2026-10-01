from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.views.decorators.cache import never_cache
from .views import LimitedLoginView
from .views import LoginForm

urlpatterns = [
    path('', views.server_status, name='status'),
    path('manager/', views.manage_server, name='manage_server'),
    path(
        'accounts/login/',
        never_cache(LimitedLoginView.as_view(
            template_name='login.html',
            authentication_form=LoginForm
        )),
        name='login'
    ),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('api/latency/', views.player_latency_js, name='player_latency_js'),
    path('api/ping/', views.ping_endpoint, name='ping_endpoint'),
    path('settings/', views.manage_settings, name='manage_settings'),
    path('assets/', views.manage_assets, name='manage_assets'),
    path('access/', views.manage_access, name='manage_access')
]
