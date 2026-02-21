import os
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import EmailVerificationToken
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
import logging

logger = logging.getLogger(__name__)

def send_verification_email(user):
    """
    Send verification email to user with a token
    """
    try:
        # Create a verification token
        token_obj = EmailVerificationToken.objects.create(user=user)
        
        # Lien vers la page frontend qui appellera l'API de vérification
        frontend_url = getattr(settings, 'FRONTEND_URL', settings.SITE_URL)
        verification_link = f"{frontend_url.rstrip('/')}/auth/verify-email/{token_obj.token}"
        
        # Prepare email content
        context = {
            'user': user,
            'verification_link': verification_link,
            'site_url': frontend_url
        }
        
        html_message = render_to_string('users/email_verification.html', context)
        plain_message = strip_tags(html_message)
        
        # Log email configuration
        logger.info(f"Attempting to send email to {user.email}")
        logger.info(f"Using SMTP host: {settings.EMAIL_HOST}")
        logger.info(f"Using SMTP port: {settings.EMAIL_PORT}")
        
        # Send email
        send_mail(
            subject='Vérifiez votre adresse email',
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Verification email sent successfully to {user.email}")
        return token_obj
        
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        # Si nous sommes en mode DEBUG, on peut continuer sans email
        if settings.DEBUG:
            logger.warning("Continuing without email verification in DEBUG mode")
            return token_obj
        raise

def send_password_reset_email(user, request=None):
    """
    Send password reset email to user with a token
    """
    # Generate token
    token_generator = PasswordResetTokenGenerator()
    token = token_generator.make_token(user)
    
    # Encode user ID
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Get site URL from environment variables
    site_url = settings.FRONTEND_URL
    
    # Create reset link - this should point to your frontend
    reset_link = f"{site_url}/auth/reset-password/{uidb64}/{token}"
    
    # Prepare email content
    context = {
        'user': user,
        'reset_link': reset_link,
        'site_url': site_url,
        'username': user.username or user.email.split('@')[0]
    }
    
    # Render email templates
    html_message = render_to_string('users/password_reset_email.html', context)
    plain_message = f"""
    Réinitialisez votre mot de passe

    Bonjour {context['username']},

    Nous avons reçu une demande de réinitialisation de mot de passe pour votre compte.
    Pour définir un nouveau mot de passe, veuillez utiliser le lien suivant :

    {reset_link}

    Ce lien est valide pendant 24 heures. Après cela, vous devrez faire une nouvelle demande de réinitialisation.

    Si vous n'avez pas demandé de réinitialisation de mot de passe, vous pouvez ignorer cet email en toute sécurité.

    Cordialement,
    L'équipe Wolof-Sign
    """
    
    # Send email
    send_mail(
        subject='Réinitialisez votre mot de passe',
        message=plain_message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False
    )
    
    return uidb64, token 