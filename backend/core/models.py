from django.db import models


class AppUser(models.Model):
    google_sub = models.CharField(max_length=255, unique=True)
    email = models.EmailField()
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'app_users'

    def __str__(self):
        return self.email
