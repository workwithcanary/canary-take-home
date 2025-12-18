import os
import hmac
import hashlib
import json
import logging
from urllib.parse import urlencode
import requests
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AppUser, GitHubAccount, GitHubRepository, GitHubWebhook, GitHubWebhookEvent

logger = logging.getLogger(__name__)

GITHUB_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_API_URL = 'https://api.github.com'


class HealthCheckView(APIView):
    def get(self, request):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class GoogleAuthView(APIView):
    def post(self, request):
        id_token = request.data.get('id_token')
        
        if not id_token:
            return Response(
                {'error': 'id_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        token_info = self._verify_google_token(id_token)
        if not token_info:
            return Response(
                {'error': 'Invalid Google token'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        google_client_id = os.getenv('GOOGLE_CLIENT_ID')
        if google_client_id and token_info.get('aud') != google_client_id:
            logger.warning('Token audience mismatch')
            return Response(
                {'error': 'Token audience mismatch'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = self._get_or_create_user(token_info)
        
        return Response({
            'id': user.id,
            'email': user.email,
            'name': user.name,
        })

    def _verify_google_token(self, id_token):
        try:
            response = requests.get(
                'https://oauth2.googleapis.com/tokeninfo',
                params={'id_token': id_token},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f'Google token verification failed: {response.status_code}')
            return None
        except requests.RequestException as e:
            logger.error(f'Google token verification error: {e}')
            return None

    def _get_or_create_user(self, token_info):
        google_sub = token_info.get('sub')
        email = token_info.get('email', '')
        name = token_info.get('name', '')

        user, created = AppUser.objects.update_or_create(
            google_sub=google_sub,
            defaults={
                'email': email,
                'name': name,
            }
        )
        
        if created:
            logger.info(f'Created new user: {email}')
        
        return user


class GitHubOAuthURLView(APIView):
    REQUIRED_SCOPES = 'read:user repo admin:repo_hook'
    
    def get(self, request):
        client_id = os.getenv('GITHUB_CLIENT_ID')
        if not client_id:
            return Response(
                {'error': 'GitHub OAuth not configured'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        force_reauth = request.query_params.get('force_reauth', 'false') == 'true'
        
        params = {
            'client_id': client_id,
            'redirect_uri': 'http://localhost:5173/auth/github/callback',
            'scope': self.REQUIRED_SCOPES,
            'state': request.query_params.get('user_id', ''),
        }
        
        if force_reauth:
            params['prompt'] = 'consent'
        
        authorize_url = f'{GITHUB_AUTHORIZE_URL}?{urlencode(params)}'
        return Response({'url': authorize_url})


class GitHubOAuthCallbackView(APIView):
    def post(self, request):
        code = request.data.get('code')
        user_id = request.data.get('user_id')
        
        if not code:
            return Response(
                {'error': 'code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = AppUser.objects.get(id=user_id)
        except AppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        token_data = self._exchange_code_for_token(code)
        if not token_data:
            return Response(
                {'error': 'Failed to exchange code for token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        access_token = token_data['access_token']
        scopes = token_data.get('scopes', [])
        
        github_user = self._fetch_github_user(access_token)
        if not github_user:
            return Response(
                {'error': 'Failed to fetch GitHub user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        github_account, created = GitHubAccount.objects.update_or_create(
            user=user,
            defaults={
                'github_user_id': github_user['id'],
                'username': github_user['login'],
                'access_token': access_token,
                'scopes': scopes,
            }
        )
        
        logger.info(f'GitHub account linked for user {user.email}: {github_user["login"]} with scopes: {scopes}')
        
        return Response({
            'username': github_account.username,
            'github_user_id': github_account.github_user_id,
            'scopes': scopes,
            'has_webhook_scope': github_account.has_webhook_scope(),
        })
    
    def _exchange_code_for_token(self, code):
        try:
            response = requests.post(
                GITHUB_TOKEN_URL,
                data={
                    'client_id': os.getenv('GITHUB_CLIENT_ID'),
                    'client_secret': os.getenv('GITHUB_CLIENT_SECRET'),
                    'code': code,
                },
                headers={'Accept': 'application/json'},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                scope_str = data.get('scope', '')
                scopes = [s.strip() for s in scope_str.split(',') if s.strip()]
                logger.info(f'GitHub token exchanged with scopes: {scopes}')
                return {
                    'access_token': access_token,
                    'scopes': scopes,
                }
            logger.warning(f'GitHub token exchange failed: {response.status_code}')
            return None
        except requests.RequestException as e:
            logger.error(f'GitHub token exchange error: {e}')
            return None
    
    def _fetch_github_user(self, access_token):
        try:
            response = requests.get(
                f'{GITHUB_API_URL}/user',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                },
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f'GitHub user fetch failed: {response.status_code}')
            return None
        except requests.RequestException as e:
            logger.error(f'GitHub user fetch error: {e}')
            return None


class GitHubStatusView(APIView):
    def get(self, request):
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = AppUser.objects.get(id=user_id)
        except AppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            github_account = user.github_account
            selected_repo = user.github_repositories.filter(is_selected=True).first()
            
            webhook_active = False
            if selected_repo and hasattr(selected_repo, 'webhook'):
                webhook_active = True
            
            return Response({
                'linked': True,
                'username': github_account.username,
                'scopes': github_account.scopes,
                'has_webhook_scope': github_account.has_webhook_scope(),
                'selected_repo': {
                    'id': selected_repo.repo_id,
                    'name': selected_repo.name,
                    'full_name': selected_repo.full_name,
                    'html_url': selected_repo.html_url,
                    'webhook_active': webhook_active,
                } if selected_repo else None
            })
        except GitHubAccount.DoesNotExist:
            return Response({
                'linked': False,
                'username': None,
                'scopes': [],
                'has_webhook_scope': False,
                'selected_repo': None
            })


class GitHubReposView(APIView):
    def get(self, request):
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = AppUser.objects.get(id=user_id)
        except AppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            github_account = user.github_account
        except GitHubAccount.DoesNotExist:
            return Response(
                {'error': 'GitHub account not linked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        repos = self._fetch_repos(github_account.access_token)
        if repos is None:
            return Response(
                {'error': 'Failed to fetch repositories'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        selected_repo = user.github_repositories.filter(is_selected=True).first()
        selected_repo_id = selected_repo.repo_id if selected_repo else None
        
        return Response({
            'repos': [
                {
                    'id': repo['id'],
                    'name': repo['name'],
                    'full_name': repo['full_name'],
                    'html_url': repo['html_url'],
                    'description': repo.get('description', ''),
                    'is_selected': repo['id'] == selected_repo_id,
                }
                for repo in repos
                if not repo.get('private', False)
            ]
        })
    
    def _fetch_repos(self, access_token):
        try:
            response = requests.get(
                f'{GITHUB_API_URL}/user/repos',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                },
                params={
                    'visibility': 'public',
                    'sort': 'updated',
                    'per_page': 100,
                },
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f'GitHub repos fetch failed: {response.status_code}')
            return None
        except requests.RequestException as e:
            logger.error(f'GitHub repos fetch error: {e}')
            return None


class GitHubRepoSelectView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        repo_id = request.data.get('repo_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not repo_id:
            return Response(
                {'error': 'repo_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = AppUser.objects.get(id=user_id)
        except AppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            github_account = user.github_account
        except GitHubAccount.DoesNotExist:
            return Response(
                {'error': 'GitHub account not linked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        repo_data, fetch_error = self._fetch_repo(github_account.access_token, repo_id)
        
        existing_repo = user.github_repositories.filter(repo_id=repo_id).first()
        
        if not repo_data:
            if existing_repo:
                logger.info(f'Using cached repo data for {existing_repo.full_name} due to API error')
                repo_data = {
                    'name': existing_repo.name,
                    'full_name': existing_repo.full_name,
                    'html_url': existing_repo.html_url,
                }
            elif fetch_error == 'network':
                return Response(
                    {'error': 'Unable to reach GitHub API. Please try again.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            else:
                return Response(
                    {'error': 'Repository not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        old_selected = user.github_repositories.filter(is_selected=True).first()
        if old_selected and old_selected.repo_id != repo_id and hasattr(old_selected, 'webhook'):
            self._delete_webhook(github_account.access_token, old_selected)
        
        user.github_repositories.update(is_selected=False)
        
        repo, created = GitHubRepository.objects.update_or_create(
            user=user,
            repo_id=repo_id,
            defaults={
                'name': repo_data['name'],
                'full_name': repo_data['full_name'],
                'html_url': repo_data['html_url'],
                'is_selected': True,
            }
        )
        
        webhook_result = self._create_webhook(github_account.access_token, repo)
        
        logger.info(f'Repository selected for user {user.email}: {repo.full_name}')
        
        return Response({
            'id': repo.repo_id,
            'name': repo.name,
            'full_name': repo.full_name,
            'html_url': repo.html_url,
            'webhook_created': webhook_result is not None,
        })
    
    def _fetch_repo(self, access_token, repo_id):
        try:
            response = requests.get(
                f'{GITHUB_API_URL}/repositories/{repo_id}',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                },
                timeout=10
            )
            if response.status_code == 200:
                return response.json(), None
            logger.warning(f'GitHub repo fetch failed: {response.status_code}')
            return None, 'not_found' if response.status_code == 404 else 'api_error'
        except requests.RequestException as e:
            logger.error(f'GitHub repo fetch error: {e}')
            return None, 'network'
    
    def _create_webhook(self, access_token, repo):
        webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
        webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:8000')
        
        if not webhook_secret:
            logger.warning('GITHUB_WEBHOOK_SECRET not configured, skipping webhook creation')
            return None
        
        if hasattr(repo, 'webhook'):
            logger.info(f'Webhook already exists for {repo.full_name}')
            return repo.webhook
        
        webhook_url = f'{webhook_base_url}/api/github/webhooks/'
        
        try:
            response = requests.post(
                f'{GITHUB_API_URL}/repos/{repo.full_name}/hooks',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                },
                json={
                    'name': 'web',
                    'active': True,
                    'events': ['push', 'pull_request'],
                    'config': {
                        'url': webhook_url,
                        'content_type': 'json',
                        'secret': webhook_secret,
                    }
                },
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                webhook = GitHubWebhook.objects.create(
                    repository=repo,
                    webhook_id=data['id']
                )
                logger.info(f'Webhook created for {repo.full_name}: {webhook.webhook_id}')
                return webhook
            elif response.status_code == 422:
                logger.warning(f'Webhook already exists on GitHub for {repo.full_name}')
                return None
            else:
                logger.warning(f'Webhook creation failed: {response.status_code} - {response.text}')
                return None
        except requests.RequestException as e:
            logger.error(f'Webhook creation error: {e}')
            return None
    
    def _delete_webhook(self, access_token, repo):
        if not hasattr(repo, 'webhook'):
            return
        
        try:
            response = requests.delete(
                f'{GITHUB_API_URL}/repos/{repo.full_name}/hooks/{repo.webhook.webhook_id}',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                },
                timeout=10
            )
            
            if response.status_code in (204, 404):
                repo.webhook.delete()
                logger.info(f'Webhook deleted for {repo.full_name}')
            else:
                logger.warning(f'Webhook deletion failed: {response.status_code}')
        except requests.RequestException as e:
            logger.error(f'Webhook deletion error: {e}')


class GitHubWebhookSetupView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = AppUser.objects.get(id=user_id)
        except AppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            github_account = user.github_account
        except GitHubAccount.DoesNotExist:
            return Response(
                {'error': 'GitHub account not linked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not github_account.has_webhook_scope():
            return Response(
                {
                    'error': 'Missing required scope: admin:repo_hook',
                    'requires_reauth': True,
                    'current_scopes': github_account.scopes,
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        selected_repo = user.github_repositories.filter(is_selected=True).first()
        if not selected_repo:
            return Response(
                {'error': 'No repository selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if hasattr(selected_repo, 'webhook'):
            return Response({
                'status': 'exists',
                'webhook_id': selected_repo.webhook.webhook_id,
                'message': 'Webhook already exists for this repository',
            })
        
        existing_hook = self._find_existing_hook(github_account.access_token, selected_repo)
        if existing_hook:
            webhook = GitHubWebhook.objects.create(
                repository=selected_repo,
                webhook_id=existing_hook['id']
            )
            logger.info(f'Reusing existing webhook for {selected_repo.full_name}: {webhook.webhook_id}')
            return Response({
                'status': 'reused',
                'webhook_id': webhook.webhook_id,
                'message': 'Reused existing webhook from GitHub',
            })
        
        webhook = self._create_webhook(github_account.access_token, selected_repo)
        if webhook:
            return Response({
                'status': 'created',
                'webhook_id': webhook.webhook_id,
                'message': 'Webhook created successfully',
            })
        
        return Response(
            {'error': 'Failed to create webhook'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    def _find_existing_hook(self, access_token, repo):
        webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:8000')
        target_url = f'{webhook_base_url}/api/github/webhooks/'
        
        try:
            response = requests.get(
                f'{GITHUB_API_URL}/repos/{repo.full_name}/hooks',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                },
                timeout=10
            )
            if response.status_code == 200:
                hooks = response.json()
                for hook in hooks:
                    if hook.get('config', {}).get('url') == target_url:
                        return hook
            return None
        except requests.RequestException as e:
            logger.error(f'Error fetching hooks: {e}')
            return None
    
    def _create_webhook(self, access_token, repo):
        webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
        webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:8000')
        
        if not webhook_secret:
            logger.warning('GITHUB_WEBHOOK_SECRET not configured')
            return None
        
        webhook_url = f'{webhook_base_url}/api/github/webhooks/'
        
        try:
            response = requests.post(
                f'{GITHUB_API_URL}/repos/{repo.full_name}/hooks',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                },
                json={
                    'name': 'web',
                    'active': True,
                    'events': ['push', 'pull_request'],
                    'config': {
                        'url': webhook_url,
                        'content_type': 'json',
                        'secret': webhook_secret,
                    }
                },
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                webhook = GitHubWebhook.objects.create(
                    repository=repo,
                    webhook_id=data['id']
                )
                logger.info(f'Webhook created for {repo.full_name}: {webhook.webhook_id}')
                return webhook
            else:
                logger.warning(f'Webhook creation failed: {response.status_code} - {response.text}')
                return None
        except requests.RequestException as e:
            logger.error(f'Webhook creation error: {e}')
            return None


class GitHubWebhookEventsView(APIView):
    def get(self, request):
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = AppUser.objects.get(id=user_id)
        except AppUser.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        selected_repo = user.github_repositories.filter(is_selected=True).first()
        if not selected_repo:
            return Response({'events': []})
        
        events = GitHubWebhookEvent.objects.filter(repository=selected_repo)[:50]
        
        return Response({
            'events': [
                {
                    'id': event.id,
                    'event_type': event.event_type,
                    'delivery_id': event.delivery_id,
                    'payload': event.payload,
                    'received_at': event.received_at.isoformat(),
                    'repo_full_name': event.repository.full_name,
                }
                for event in events
            ]
        })


@method_decorator(csrf_exempt, name='dispatch')
class GitHubWebhookReceiverView(View):
    """
    Receives incoming webhook events from GitHub.
    
    Security: Uses HMAC-SHA256 signature validation.
    Storage: Raw payloads stored idempotently by delivery_id.
    Processing: None - events are logged and acknowledged only.
    """
    
    def post(self, request):
        """
        Receives webhook events from GitHub.
        Validates signature, parses payload, stores event, returns 200 immediately.
        """
        signature = request.headers.get('X-Hub-Signature-256')
        event_type = request.headers.get('X-GitHub-Event')
        delivery_id = request.headers.get('X-GitHub-Delivery')
        content_type = request.headers.get('Content-Type', '')
        
        raw_body = request.body
        
        logger.info(f'[WEBHOOK] {event_type} received, delivery: {delivery_id}')
        
        # Signature validation is mandatory
        if not signature:
            logger.warning('[WEBHOOK] Missing signature')
            return JsonResponse({'error': 'Missing signature'}, status=401)
        
        if not self._verify_signature(raw_body, signature):
            logger.warning(f'[WEBHOOK] Invalid signature for {delivery_id}')
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Parse payload (handle both JSON and form-urlencoded)
        try:
            if 'application/x-www-form-urlencoded' in content_type:
                import urllib.parse
                parsed = urllib.parse.parse_qs(raw_body.decode('utf-8'))
                payload_str = parsed.get('payload', [''])[0]
                if not payload_str:
                    return JsonResponse({'error': 'Missing payload field'}, status=400)
                payload = json.loads(payload_str)
            else:
                payload = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.warning(f'[WEBHOOK] Invalid JSON: {e}')
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        repo_full_name = payload.get('repository', {}).get('full_name', 'unknown')
        repo_id = payload.get('repository', {}).get('id')
        
        if event_type == 'push':
            ref = payload.get('ref', '')
            commits_count = len(payload.get('commits', []))
            pusher = payload.get('pusher', {}).get('name', 'unknown')
            logger.info(f'[WEBHOOK] push to {repo_full_name} - ref: {ref}, commits: {commits_count}, by: {pusher}')
        
        elif event_type == 'pull_request':
            action = payload.get('action', '')
            pr_number = payload.get('number', '')
            pr_title = payload.get('pull_request', {}).get('title', '')
            merged = payload.get('pull_request', {}).get('merged', False)
            
            if action == 'closed' and merged:
                logger.info(f'[WEBHOOK] pull_request MERGED on {repo_full_name} - #{pr_number}: {pr_title}')
            else:
                logger.info(f'[WEBHOOK] pull_request {action} on {repo_full_name} - #{pr_number}: {pr_title}')
        
        elif event_type == 'ping':
            zen = payload.get('zen', '')
            hook_id = payload.get('hook_id', '')
            logger.info(f'[WEBHOOK] ping received for {repo_full_name} - hook_id: {hook_id}, zen: {zen}')
        
        else:
            logger.info(f'[WEBHOOK] {event_type} received for {repo_full_name}')
        
        if repo_id and delivery_id and event_type != 'ping':
            self._store_event(repo_id, event_type, delivery_id, payload)
        
        return JsonResponse({'status': 'received'}, status=200)
    
    def _store_event(self, repo_id, event_type, delivery_id, payload):
        try:
            repo = GitHubRepository.objects.filter(repo_id=repo_id).first()
            if not repo:
                logger.warning(f'[WEBHOOK] Repository not found in DB: {repo_id}')
                return
            
            event, created = GitHubWebhookEvent.objects.get_or_create(
                delivery_id=delivery_id,
                defaults={
                    'repository': repo,
                    'event_type': event_type,
                    'payload': payload,
                }
            )
            
            if created:
                logger.info(f'[WEBHOOK] Event stored: {event_type} for {repo.full_name}')
            else:
                logger.info(f'[WEBHOOK] Event already exists: {delivery_id}')
        except Exception as e:
            logger.error(f'[WEBHOOK] Error storing event: {e}')
    
    def _verify_signature(self, payload_body, signature_header):
        webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET')
        
        if not webhook_secret:
            logger.error('GITHUB_WEBHOOK_SECRET not configured')
            return False
        
        if not signature_header.startswith('sha256='):
            return False
        
        expected_signature = 'sha256=' + hmac.new(
            webhook_secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature_header)
