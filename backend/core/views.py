import os
import logging
from urllib.parse import urlencode
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AppUser, GitHubAccount, GitHubRepository

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
    def get(self, request):
        client_id = os.getenv('GITHUB_CLIENT_ID')
        if not client_id:
            return Response(
                {'error': 'GitHub OAuth not configured'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        params = {
            'client_id': client_id,
            'redirect_uri': 'http://localhost:5173/auth/github/callback',
            'scope': 'read:user repo',
            'state': request.query_params.get('user_id', ''),
        }
        
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
        
        access_token = self._exchange_code_for_token(code)
        if not access_token:
            return Response(
                {'error': 'Failed to exchange code for token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
            }
        )
        
        logger.info(f'GitHub account linked for user {user.email}: {github_user["login"]}')
        
        return Response({
            'username': github_account.username,
            'github_user_id': github_account.github_user_id,
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
                return data.get('access_token')
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
            return Response({
                'linked': True,
                'username': github_account.username,
                'selected_repo': {
                    'id': selected_repo.repo_id,
                    'name': selected_repo.name,
                    'full_name': selected_repo.full_name,
                    'html_url': selected_repo.html_url,
                } if selected_repo else None
            })
        except GitHubAccount.DoesNotExist:
            return Response({
                'linked': False,
                'username': None,
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
        
        repo_data = self._fetch_repo(github_account.access_token, repo_id)
        if not repo_data:
            return Response(
                {'error': 'Repository not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
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
        
        logger.info(f'Repository selected for user {user.email}: {repo.full_name}')
        
        return Response({
            'id': repo.repo_id,
            'name': repo.name,
            'full_name': repo.full_name,
            'html_url': repo.html_url,
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
                return response.json()
            logger.warning(f'GitHub repo fetch failed: {response.status_code}')
            return None
        except requests.RequestException as e:
            logger.error(f'GitHub repo fetch error: {e}')
            return None
