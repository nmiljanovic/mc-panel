from django.db import models
from django.conf import settings


class OnlinePlayer(models.Model):
    username = models.CharField(max_length=16, unique=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    @property
    def avatar(self):
        avatar_url = settings.AVATAR_URL
        return f"{avatar_url}{self.username}/32.png"

    def __str__(self):
        return self.username
