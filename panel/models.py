from django.db import models


class OnlinePlayer(models.Model):
    username = models.CharField(max_length=100, unique=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username
