from django.urls import path
from . import views
from .views import LoginForm
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path(
        'accounts/login/',
        auth_views.LoginView.as_view(
            template_name='login.html',
            authentication_form=LoginForm
        ),
        name='login'
    ),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('settings/', views.manage_settings, name='manage_settings'),
    path('assets/', views.manage_assets, name='manage_assets'),
    path('access/', views.manage_access, name='manage_access')
]
