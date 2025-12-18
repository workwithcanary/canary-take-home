import os
import logging
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AppUser

logger = logging.getLogger(__name__)


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
