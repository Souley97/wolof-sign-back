# urls.py
from django.urls import path
from .views import (
    register_user, 
    LoginView, 
    LogoutView,
    UserListView, 
    verify_email, 
    resend_verification_email,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    UserProfileView
)

urlpatterns = [
    path('register/', register_user, name='register_user'),
    path('login/', LoginView.as_view(), name='login_user'),
    path('logout/', LogoutView.as_view(), name='lougout_user'),
    
    path('users/', UserListView.as_view(), name='user_list'),
    path('verify-email/<str:token>/', verify_email, name='verify_email'),
    path('resend-verification-email/', resend_verification_email, name='resend_verification_email'),
    path('reset-password-request/', PasswordResetRequestView.as_view(), name='reset_password_request'),
    path('reset-password-confirm/<str:uidb64>/<str:token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
]
