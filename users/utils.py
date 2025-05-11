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

def send_verification_email(user):
    """
    Send verification email to user with a token
    """
    # Create a verification token
    token_obj = EmailVerificationToken.objects.create(user=user)
    
    # Get site URL from environment variables
    site_url = settings.SITE_URL
    
    # Create verification link
    verification_link = f"{site_url}/api/user/verify-email/{token_obj.token}/"
    
    # Prepare email content
    context = {
        'user': user,
        'verification_link': verification_link,
        'site_url': site_url
    }
    
    html_message = render_to_string('users/email_verification.html', context)
    plain_message = strip_tags(html_message)
    
    # Send email
    send_mail(
        subject='Vérifiez votre adresse email',
        message=plain_message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False
    )
    
    return token_obj

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
    site_url = settings.SITE_URL
    
    # Create reset link - this should point to your frontend
    reset_link = f"http://localhost:3000/auth/reset-password/{uidb64}/{token}"
    
    # Prepare email content
    context = {
        'user': user,
        'reset_link': reset_link,
        'site_url': site_url
    }
    
    # Render email templates
    html_message = render_to_string('users/password_reset_email.html', context)
    plain_message = strip_tags(html_message)
    
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