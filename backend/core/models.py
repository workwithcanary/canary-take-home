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
    scopes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'github_accounts'

    def __str__(self):
        return self.username

    def has_webhook_scope(self):
        return 'admin:repo_hook' in self.scopes


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


class GitHubWebhook(models.Model):
    repository = models.OneToOneField(
        GitHubRepository,
        on_delete=models.CASCADE,
        related_name='webhook'
    )
    webhook_id = models.BigIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'github_webhooks'

    def __str__(self):
        return f'Webhook {self.webhook_id} for {self.repository.full_name}'


class GitHubWebhookEvent(models.Model):
    repository = models.ForeignKey(
        GitHubRepository,
        on_delete=models.CASCADE,
        related_name='webhook_events'
    )
    event_type = models.CharField(max_length=100)
    delivery_id = models.CharField(max_length=100, unique=True)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'github_webhook_events'
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.event_type} for {self.repository.full_name} at {self.received_at}'
