from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    stripe_webhook, plans_list_api, current_subscription_api, 
    change_plan_api, cancel_subscription_api, usage_stats_api,
    PlanViewSet, SubscriptionAdminViewSet, PaymentHistoryViewSet,
    SubscriptionStatsView, sync_stripe_plans, reset_usage_counters,
    extend_subscription_period, paydunya_webhook, paydunya_checkout_api,
    check_payment_status_api
)

# Configurer les routeurs pour les vues ModelViewSet
router = DefaultRouter()
router.register(r'admin/plans', PlanViewSet, basename='admin-plan')
router.register(r'admin/subscriptions', SubscriptionAdminViewSet, basename='admin-subscription')
router.register(r'admin/payments', PaymentHistoryViewSet, basename='admin-payment')

urlpatterns = [
    # Webhook Stripe
    path('webhook/stripe/', stripe_webhook, name='stripe_webhook'),
    
    # Webhook PayDunya
    path('webhook/paydunya/', paydunya_webhook, name='paydunya_webhook'),
    
    # API pour utilisateurs finaux
    path('plans/', plans_list_api, name='api_plans_list'),
    path('current/', current_subscription_api, name='api_current_subscription'),
    path('change-plan/<int:plan_id>/', change_plan_api, name='api_change_plan'),
    path('cancel/', cancel_subscription_api, name='api_cancel_subscription'),
    path('usage/', usage_stats_api, name='api_usage_stats'),
    
    # API PayDunya pour utilisateurs finaux
    path('paydunya-checkout/<int:plan_id>/', paydunya_checkout_api, name='api_paydunya_checkout'),
    path('check-payment-status/<str:token>/', check_payment_status_api, name='api_check_payment_status'),
    
    # API de débogage (utilitaires)
    
    # API d'administration
    path('', include(router.urls)),
    path('admin/stats/', SubscriptionStatsView.as_view(), name='admin_subscription_stats'),
    path('admin/sync-stripe-plans/', sync_stripe_plans, name='admin_sync_stripe_plans'),
    path('admin/reset-usage/<int:subscription_id>/', reset_usage_counters, name='admin_reset_usage'),
    path('admin/extend-period/<int:subscription_id>/', extend_subscription_period, name='admin_extend_period'),
]
