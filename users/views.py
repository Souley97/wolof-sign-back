from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from django.contrib.auth import get_user_model
from .serializers import (
    UserSerializer, 
    CustomTokenObtainPairSerializer,
    PasswordResetRequestSerializer,
    SetNewPasswordSerializer,
    ChangePasswordSerializer,
    LogoutSerializer
)
import logging
from rest_framework_simplejwt.views import TokenObtainPairView
# from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .serializers import CustomTokenObtainPairSerializer

from rest_framework import generics
# from rest_framework.permissions import IsAdminUser
from .utils import send_verification_email, send_password_reset_email
from .models import EmailVerificationToken
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import redirect
from .renderers import UserRenderer
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from .serializers import *
from django.utils.encoding import smart_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from .utils import *
from rest_framework import generics, permissions, status
from django.utils.encoding import force_str
from django.conf import settings

logger = logging.getLogger(__name__)

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def register_user(request):
    try:
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Send verification email
            try:
                send_verification_email(user)
                logger.info(f"Verification email sent to: {user.email}")
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
                # Continue with registration even if email fails
            
            logger.info(f"New user registered: {user.email}")
            return Response({
                "message": "Inscription réussie. Veuillez vérifier votre email pour activer votre compte.",
                "user": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error during user registration: {str(e)}")
        return Response(
            {"error": "Une erreur est survenue lors de l'inscription"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    try:
        # Find token in database
        token_obj = get_object_or_404(EmailVerificationToken, token=token)
        
        # Check if token is still valid
        if not token_obj.is_valid():
            return Response(
                {"error": "Le lien de vérification a expiré. Veuillez demander un nouveau lien de vérification."},
                status=status.HTTP_400_BAD_REQUEST
                # redirect
            )
        
        # Mark user as verified
        user = token_obj.user
        if not user.is_verified:
            user.is_verified = True
            user.save()
            
            # Delete the token after use
            token_obj.delete()
            site_url = settings.FRONTEND_URL
    
    
    # Create reset link - this should point to your frontend
    
            redirection_url = f"{site_url}/auth/login"
            return redirect(redirection_url)
        
        
            return Response(
                {"message": "Votre email a été vérifié avec succès. Vous pouvez maintenant vous connecter à votre compte."},
                status=status.HTTP_200_OK
                
            )
        else:
            return Response(
                {"message": "Votre email a déjà été vérifié. Vous pouvez vous connecter à votre compte."},
                status=status.HTTP_200_OK
            )
            
    except EmailVerificationToken.DoesNotExist:
        return Response(
            {"error": "Le lien de vérification est invalide ou a déjà été utilisé."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        return Response(
            {"error": "Une erreur est survenue lors de la vérification de l'email. Veuillez réessayer plus tard."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_email(request):
    try:
        email = request.data.get('email')
        if not email:
            return Response(
                {"error": "L'adresse email est requise"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            user = get_object_or_404(User, email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Aucun utilisateur trouvé avec cette adresse email"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if user.is_verified:
            return Response(
                {"message": "Votre email a déjà été vérifié. Vous pouvez vous connecter dès maintenant."},
                status=status.HTTP_200_OK
            )
            
        # Delete existing tokens
        EmailVerificationToken.objects.filter(user=user).delete()
        
        # Send new verification email
        try:
            send_verification_email(user)
            return Response(
                {"message": "Un nouveau lien de vérification a été envoyé à votre adresse email."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Erreur d'envoi d'email: {str(e)}", exc_info=True)
            err_msg = "Impossible d'envoyer l'email de vérification. Veuillez réessayer plus tard."
            if getattr(settings, 'DEBUG', False):
                err_msg += f" (détail: {str(e)})"
            return Response(
                {"error": err_msg},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    except Exception as e:
        logger.error(f"Error during resend verification: {str(e)}")
        return Response(
            {"error": "Une erreur est survenue lors de l'envoi du mail de vérification"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
# login


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Use the custom serializer to handle login
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data)
    
# profile
class UserListView(generics.ListAPIView):
    queryset = User.objects.exclude(is_staff=True)
    serializer_class = UserSerializer
    # permission_classes = [IsAdminUser]
    

class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data, context={'request': request})
            
            if serializer.is_valid():
                email = serializer.validated_data['email']
                try:
                    user = User.objects.get(email=email)
                    
                    # Envoyer l'email de réinitialisation
                    uid, token = send_password_reset_email(user, request)
                    
                    return Response(
                        {
                            "message": "Un email de réinitialisation de mot de passe a été envoyé à votre adresse email.",
                            "uid": uid,
                            "token": token
                        }, 
                        status=status.HTTP_200_OK
                    )
                except User.DoesNotExist:
                    return Response(
                        {"error": "Aucun compte n'est associé à cette adresse email."},
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Erreur lors de la demande de réinitialisation de mot de passe: {str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la demande de réinitialisation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = SetNewPasswordSerializer
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]

    def patch(self, request, uidb64, token, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                try:
                    # Décoder l'ID utilisateur
                    user_id = smart_str(urlsafe_base64_decode(uidb64))
                    user = User.objects.get(id=user_id)
                    
                    # Vérifier que le token est valide
                    if not PasswordResetTokenGenerator().check_token(user, token):
                        return Response(
                            {'error': "Le lien de réinitialisation est invalide ou a expiré."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Réinitialiser le mot de passe
                    user.set_password(serializer.validated_data['password'])
                    user.save()
                    
                    return Response(
                        {"message": "Votre mot de passe a été réinitialisé avec succès."},
                        status=status.HTTP_200_OK
                    )
                except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                    return Response(
                        {'error': "Le lien de réinitialisation est invalide ou a expiré."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Erreur lors de la réinitialisation du mot de passe: {str(e)}")
            return Response(
                {"error": "Une erreur est survenue lors de la réinitialisation du mot de passe."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChangePasswordView(generics.GenericAPIView):
    """
    Endpoint pour changer le mot de passe.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [AllowAny]  # À changer en IsAuthenticated en production
    
    def get_object(self):
        return self.request.user
    
    def post(self, request, *args, **kwargs):
        """
        Gère les requêtes POST pour changer le mot de passe
        """
        return self._change_password(request)
    
    def patch(self, request, *args, **kwargs):
        """
        Gère les requêtes PATCH pour changer le mot de passe
        """
        return self._change_password(request)
    
    def put(self, request, *args, **kwargs):
        """
        Gère les requêtes PUT pour changer le mot de passe
        """
        return self._change_password(request)
    
    def _change_password(self, request):
        """
        Logique commune pour changer le mot de passe
        """
        serializer = self.get_serializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    'status': 'success',
                    'message': 'Mot de passe mis à jour avec succès',
                }, 
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View pour récupérer et mettre à jour le profil utilisateur
    """
    serializer_class = UserSerializer
    permission_classes = [AllowAny]  # À modifier pour utiliser IsAuthenticated en production
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Ne pas permettre la modification de l'email via cette vue
        if 'email' in request.data:
            del request.data['email']
            
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Profil mis à jour avec succès", "data": serializer.data},
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
    # logout
class LogoutView(generics.GenericAPIView):
    """ 
    View pour la déconnexion de l'utilisateur
    """
    serializer_class = LogoutSerializer
    permission_classes = [AllowAny]  # À modifier pour utiliser IsAuthenticated en production
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Logique de déconnexion (par exemple, supprimer le token)
        # ...
        
        return Response(
            {"message": "Déconnexion réussie"},
            status=status.HTTP_200_OK
        )
        
# class LogoutAPIView(generics.GenericAPIView):
#     serializer_class = LogoutSerializer
#     permission_classes = [permissions.IsAuthenticated]
#     renderer_classes = [UserRenderer]

#     def post(self, request):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response({"message": "Vous vous êtes déconnecté avec succès."}, status=status.HTTP_204_NO_CONTENT)