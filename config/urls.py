from django.urls import path, include

urlpatterns = [
    # This goes last, look inside panel.urls
    path('', include('panel.urls')),
]
