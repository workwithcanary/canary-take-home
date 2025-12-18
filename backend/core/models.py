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


class GitHubAccount(models.Model):
    user = models.OneToOneField(
        AppUser,
        on_delete=models.CASCADE,
        related_name='github_account'
    )
    github_user_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255)
    access_token = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'github_accounts'

    def __str__(self):
        return self.username


class GitHubRepository(models.Model):
    user = models.ForeignKey(
        AppUser,
        on_delete=models.CASCADE,
        related_name='github_repositories'
    )
    repo_id = models.BigIntegerField()
    name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=512)
    html_url = models.URLField()
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'github_repositories'
        unique_together = ['user', 'repo_id']

    def __str__(self):
        return self.full_name
