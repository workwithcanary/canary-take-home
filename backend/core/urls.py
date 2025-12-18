from django.urls import path
from .views import HealthCheckView, GoogleAuthView

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
]
