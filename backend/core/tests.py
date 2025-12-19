"""
Unit tests for critical backend behavior.
Covers OAuth logic, webhook receiver, and webhook setup.
"""
import json
import hmac
import hashlib
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework import status

from .models import AppUser, GitHubAccount, GitHubRepository, GitHubWebhook, GitHubWebhookEvent


class GoogleAuthTests(APITestCase):
    """Tests for Google OAuth token verification and user creation."""
    
    def test_missing_token_returns_400(self):
        """Request without id_token should return 400."""
        response = self.client.post('/api/auth/google/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'id_token is required')
    
    @patch('core.views.requests.get')
    def test_invalid_token_returns_401(self, mock_get):
        """Invalid Google token should return 401."""
        mock_get.return_value = MagicMock(status_code=400)
        
        response = self.client.post('/api/auth/google/', {'id_token': 'invalid-token'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error'], 'Invalid Google token')
    
    @patch('core.views.requests.get')
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-client-id'})
    def test_valid_token_creates_user(self, mock_get):
        """Valid Google token should create a new user."""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'sub': 'google-123',
                'email': 'test@example.com',
                'name': 'Test User',
                'aud': 'test-client-id',
            }
        )
        
        response = self.client.post('/api/auth/google/', {'id_token': 'valid-token'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['name'], 'Test User')
        
        # Verify user was created
        self.assertTrue(AppUser.objects.filter(google_sub='google-123').exists())
    
    @patch('core.views.requests.get')
    @patch.dict('os.environ', {'GOOGLE_CLIENT_ID': 'test-client-id'})
    def test_valid_token_updates_existing_user(self, mock_get):
        """Valid token for existing user should update their info."""
        # Create existing user
        AppUser.objects.create(google_sub='google-123', email='old@example.com', name='Old Name')
        
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'sub': 'google-123',
                'email': 'new@example.com',
                'name': 'New Name',
                'aud': 'test-client-id',
            }
        )
        
        response = self.client.post('/api/auth/google/', {'id_token': 'valid-token'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user = AppUser.objects.get(google_sub='google-123')
        self.assertEqual(user.email, 'new@example.com')
        self.assertEqual(user.name, 'New Name')


class GitHubOAuthCallbackTests(APITestCase):
    """Tests for GitHub OAuth callback and token exchange."""
    
    def setUp(self):
        self.user = AppUser.objects.create(
            google_sub='google-123',
            email='test@example.com',
            name='Test User'
        )
    
    def test_missing_code_returns_400(self):
        """Request without code should return 400."""
        response = self.client.post('/api/github/oauth/callback/', {'user_id': self.user.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'code is required')
    
    def test_missing_user_id_returns_400(self):
        """Request without user_id should return 400."""
        response = self.client.post('/api/github/oauth/callback/', {'code': 'test-code'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'user_id is required')
    
    def test_invalid_user_id_returns_404(self):
        """Request with invalid user_id should return 404."""
        response = self.client.post('/api/github/oauth/callback/', {
            'code': 'test-code',
            'user_id': 99999
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @patch('core.views.requests.get')
    @patch('core.views.requests.post')
    def test_token_exchange_failure_returns_400(self, mock_post, mock_get):
        """Failed token exchange should return 400."""
        mock_post.return_value = MagicMock(status_code=400)
        
        response = self.client.post('/api/github/oauth/callback/', {
            'code': 'invalid-code',
            'user_id': self.user.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Failed to exchange code for token')
    
    @patch('core.views.requests.get')
    @patch('core.views.requests.post')
    def test_successful_oauth_stores_scopes(self, mock_post, mock_get):
        """Successful OAuth should store scopes from token response."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'access_token': 'gho_test123',
                'scope': 'read:user,repo,admin:repo_hook'
            }
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'id': 12345,
                'login': 'testuser'
            }
        )
        
        response = self.client.post('/api/github/oauth/callback/', {
            'code': 'valid-code',
            'user_id': self.user.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertTrue(response.data['has_webhook_scope'])
        
        # Verify scopes were stored
        github_account = GitHubAccount.objects.get(user=self.user)
        self.assertIn('admin:repo_hook', github_account.scopes)


class WebhookReceiverTests(TestCase):
    """Tests for GitHub webhook receiver endpoint."""
    
    def setUp(self):
        self.webhook_secret = 'test-secret-key'
        self.user = AppUser.objects.create(
            google_sub='google-123',
            email='test@example.com',
            name='Test User'
        )
        self.repo = GitHubRepository.objects.create(
            user=self.user,
            repo_id=12345,
            name='test-repo',
            full_name='testuser/test-repo',
            html_url='https://github.com/testuser/test-repo',
            is_selected=True
        )
    
    def _sign_payload(self, payload: bytes, secret: str) -> str:
        """Generate HMAC SHA-256 signature for payload."""
        signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return f'sha256={signature}'
    
    @override_settings()
    @patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'test-secret-key'})
    def test_missing_signature_returns_401(self):
        """Request without signature should return 401."""
        response = self.client.post(
            '/api/github/webhooks/',
            data=json.dumps({'test': 'data'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Missing signature')
    
    @patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'test-secret-key'})
    def test_invalid_signature_returns_401(self):
        """Request with invalid signature should return 401."""
        payload = json.dumps({'test': 'data'}).encode()
        
        response = self.client.post(
            '/api/github/webhooks/',
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=invalid',
            HTTP_X_GITHUB_EVENT='push',
            HTTP_X_GITHUB_DELIVERY='test-delivery-id'
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Invalid signature')
    
    @patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'test-secret-key'})
    def test_valid_signature_returns_200(self):
        """Request with valid signature should return 200."""
        payload = json.dumps({
            'repository': {'id': 12345, 'full_name': 'testuser/test-repo'},
            'ref': 'refs/heads/main',
            'commits': []
        }).encode()
        signature = self._sign_payload(payload, 'test-secret-key')
        
        response = self.client.post(
            '/api/github/webhooks/',
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature,
            HTTP_X_GITHUB_EVENT='push',
            HTTP_X_GITHUB_DELIVERY='test-delivery-123'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'received')
    
    @patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'test-secret-key'})
    def test_push_event_stored_in_database(self):
        """Push event should be stored in database."""
        payload = json.dumps({
            'repository': {'id': 12345, 'full_name': 'testuser/test-repo'},
            'ref': 'refs/heads/main',
            'commits': [{'id': 'abc123'}],
            'pusher': {'name': 'testuser'}
        }).encode()
        signature = self._sign_payload(payload, 'test-secret-key')
        
        response = self.client.post(
            '/api/github/webhooks/',
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature,
            HTTP_X_GITHUB_EVENT='push',
            HTTP_X_GITHUB_DELIVERY='unique-delivery-id-1'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            GitHubWebhookEvent.objects.filter(delivery_id='unique-delivery-id-1').exists()
        )
    
    @patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'test-secret-key'})
    def test_duplicate_delivery_id_ignored(self):
        """Duplicate delivery_id should not create duplicate event."""
        # Create existing event
        GitHubWebhookEvent.objects.create(
            repository=self.repo,
            event_type='push',
            delivery_id='duplicate-delivery-id',
            payload={'existing': True}
        )
        
        payload = json.dumps({
            'repository': {'id': 12345, 'full_name': 'testuser/test-repo'},
            'ref': 'refs/heads/main',
            'commits': []
        }).encode()
        signature = self._sign_payload(payload, 'test-secret-key')
        
        response = self.client.post(
            '/api/github/webhooks/',
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature,
            HTTP_X_GITHUB_EVENT='push',
            HTTP_X_GITHUB_DELIVERY='duplicate-delivery-id'
        )
        
        self.assertEqual(response.status_code, 200)
        # Should still only have one event with this delivery_id
        self.assertEqual(
            GitHubWebhookEvent.objects.filter(delivery_id='duplicate-delivery-id').count(),
            1
        )
    
    @patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'test-secret-key'})
    def test_ping_event_not_stored(self):
        """Ping events should be acknowledged but not stored."""
        payload = json.dumps({
            'zen': 'Keep it simple',
            'hook_id': 12345,
            'repository': {'id': 12345, 'full_name': 'testuser/test-repo'}
        }).encode()
        signature = self._sign_payload(payload, 'test-secret-key')
        
        initial_count = GitHubWebhookEvent.objects.count()
        
        response = self.client.post(
            '/api/github/webhooks/',
            data=payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature,
            HTTP_X_GITHUB_EVENT='ping',
            HTTP_X_GITHUB_DELIVERY='ping-delivery-id'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GitHubWebhookEvent.objects.count(), initial_count)


class WebhookSetupTests(APITestCase):
    """Tests for webhook setup endpoint."""
    
    def setUp(self):
        self.user = AppUser.objects.create(
            google_sub='google-123',
            email='test@example.com',
            name='Test User'
        )
        self.repo = GitHubRepository.objects.create(
            user=self.user,
            repo_id=12345,
            name='test-repo',
            full_name='testuser/test-repo',
            html_url='https://github.com/testuser/test-repo',
            is_selected=True
        )
    
    def test_missing_user_id_returns_400(self):
        """Request without user_id should return 400."""
        response = self.client.post('/api/github/webhooks/setup/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_no_github_account_returns_400(self):
        """User without GitHub account should return 400."""
        response = self.client.post('/api/github/webhooks/setup/', {'user_id': self.user.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'GitHub account not linked')
    
    def test_missing_webhook_scope_returns_403(self):
        """User without admin:repo_hook scope should return 403."""
        GitHubAccount.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
            access_token='test-token',
            scopes=['read:user', 'repo']  # Missing admin:repo_hook
        )
        
        response = self.client.post('/api/github/webhooks/setup/', {'user_id': self.user.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.data['requires_reauth'])
    
    def test_existing_webhook_returns_exists(self):
        """If webhook already exists locally, return 'exists' status."""
        GitHubAccount.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
            access_token='test-token',
            scopes=['admin:repo_hook']
        )
        GitHubWebhook.objects.create(
            repository=self.repo,
            webhook_id=99999
        )
        
        response = self.client.post('/api/github/webhooks/setup/', {'user_id': self.user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'exists')
        self.assertEqual(response.data['webhook_id'], 99999)
    
    @patch('core.views.requests.get')
    @patch('core.views.requests.post')
    @patch.dict('os.environ', {
        'GITHUB_WEBHOOK_SECRET': 'test-secret',
        'WEBHOOK_BASE_URL': 'https://example.com'
    })
    def test_reuses_existing_github_hook(self, mock_post, mock_get):
        """Should reuse existing webhook from GitHub if URL matches."""
        GitHubAccount.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
            access_token='test-token',
            scopes=['admin:repo_hook']
        )
        
        # Mock finding existing hook
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {
                    'id': 88888,
                    'config': {'url': 'https://example.com/api/github/webhooks/'}
                }
            ]
        )
        
        response = self.client.post('/api/github/webhooks/setup/', {'user_id': self.user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'reused')
        self.assertEqual(response.data['webhook_id'], 88888)
        
        # Verify webhook was saved
        self.assertTrue(GitHubWebhook.objects.filter(webhook_id=88888).exists())
    
    @patch('core.views.requests.get')
    @patch('core.views.requests.post')
    @patch.dict('os.environ', {
        'GITHUB_WEBHOOK_SECRET': 'test-secret',
        'WEBHOOK_BASE_URL': 'https://example.com'
    })
    def test_creates_new_webhook_if_none_exists(self, mock_post, mock_get):
        """Should create new webhook if none exists on GitHub."""
        GitHubAccount.objects.create(
            user=self.user,
            github_user_id=12345,
            username='testuser',
            access_token='test-token',
            scopes=['admin:repo_hook']
        )
        
        # Mock no existing hooks
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: []
        )
        # Mock successful webhook creation
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {'id': 77777}
        )
        
        response = self.client.post('/api/github/webhooks/setup/', {'user_id': self.user.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'created')
        self.assertEqual(response.data['webhook_id'], 77777)

