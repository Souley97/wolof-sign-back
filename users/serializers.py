from rest_framework import serializers
from .models import User
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import authenticate, get_user_model

from rest_framework_simplejwt.tokens import RefreshToken, TokenError

import logging
from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _


from .utils import send_mail

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
    
    # Add a custom validation for the username field
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

# login
class LoginView(TokenObtainPairView):
    serializer_class = TokenObtainPairSerializer
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        return Response({
            'access': serializer.validated_data['access'],  # Correct access token
            'refresh': serializer.validated_data['refresh'], 
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,

        })



# Custom validation for username field to ensure it's unique
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email is None:
            raise serializers.ValidationError('Email requis.')
        if password is None:
            raise serializers.ValidationError('Mot de passe requis.')

        try:
            user = get_user_model().objects.get(email=email)

            if not user.check_password(password):
                raise serializers.ValidationError("Identifiants invalides. Veuillez vérifier votre email et mot de passe.")
            
            if not user.is_verified:
                raise serializers.ValidationError("Votre email n'a pas été vérifié. Veuillez vérifier votre boîte de réception.")

        except get_user_model().DoesNotExist:
            raise serializers.ValidationError("Aucun compte ne correspond à cet email.")

        refresh_token = self.get_token(user)
        access_token = str(refresh_token.access_token)
        refresh_token_str = str(refresh_token)

        return {
            'access': access_token,
            'refresh': refresh_token_str,
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
        }

    class Meta:
        model = get_user_model()
        fields = ('email', 'password')
        
        
class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for requesting a password reset.
    """
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_('Aucun utilisateur trouvé avec cette adresse email.'))
        return value

    def save(self):
        request = self.context.get('request')
        user = User.objects.get(email=self.validated_data['email'])
        token = PasswordResetTokenGenerator().make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        current_site = get_current_site(request).domain
        relative_link = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        abs_url = f'http://{current_site}{relative_link}'
        email_body = f'Hi {user.username},\n\n Vous pouver utiliser ce lien pour modifier le mot de passe:\n{abs_url}'
        data = {
            'email_subject': 'Modifier le mot de passe ',
            'email_body': email_body,
            'to_email': user.email,
        }

        send_email(data)

class SetNewPasswordSerializer(serializers.Serializer):
    """
    Serializer for setting a new password.
    """
    password = serializers.CharField(min_length=6, write_only=True)

    class Meta:
        fields = ['password']

class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
    """
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate_new_password(self, value):
        """
        Validate that the new password meets the necessary criteria.
        """
        validate_password(value)
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        logger.debug(f'User: {user}, Old Password: {attrs["old_password"]}')
        if not user.check_password(attrs['old_password']):
            logger.warning("L'ancien mot de passe est incorrect")
            raise serializers.ValidationError({"old_password": _("L'ancien mot de passe n'est pas correct")})

        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({"new_password": _("Le nouveau mot de passe ne peut pas être identique à l'ancien mot de passe")})

        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
    
# logout
class LogoutSerializer(serializers.Serializer):
    """
    Serializer for user logout.
    """
    refresh = serializers.CharField()

    default_error_messages = {
        'bad_token': _('Token is expired or invalid')
    }

    def validate(self, attrs):
        self.token = attrs['refresh']
        return attrs

    def save(self, **kwargs):
        try:
            refresh_token = RefreshToken(self.token)
            refresh_token.blacklist()
        except TokenError:
            self.fail('bad_token')