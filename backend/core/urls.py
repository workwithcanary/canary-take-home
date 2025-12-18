from django.urls import path
from .views import (
    HealthCheckView,
    GoogleAuthView,
    GitHubOAuthURLView,
    GitHubOAuthCallbackView,
    GitHubStatusView,
    GitHubReposView,
    GitHubRepoSelectView,
    GitHubWebhookReceiverView,
)

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('github/oauth/url/', GitHubOAuthURLView.as_view(), name='github-oauth-url'),
    path('github/oauth/callback/', GitHubOAuthCallbackView.as_view(), name='github-oauth-callback'),
    path('github/status/', GitHubStatusView.as_view(), name='github-status'),
    path('github/repos/', GitHubReposView.as_view(), name='github-repos'),
    path('github/repos/select/', GitHubRepoSelectView.as_view(), name='github-repo-select'),
    path('github/webhooks/', GitHubWebhookReceiverView.as_view(), name='github-webhooks'),
]
