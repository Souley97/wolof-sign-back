from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
import json
import logging

from .models import Plan, Subscription, PaymentHistory
from .serializers import (
    PlanSerializer, SubscriptionSerializer, PaymentHistorySerializer,
    SubscriptionUpdateSerializer, PlanUpdateSerializer, SubscriptionAdminSerializer
)
from .stripe_service import StripeService
from .services.paydunya_service import PayDunyaService


# ======= CRUD ADMIN VIEWS =======

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class PlanViewSet(viewsets.ModelViewSet):
    """Gestion complète des plans d'abonnement pour l'administration"""
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    # permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'plan_type', 'has_api_access']
    search_fields = ['name', 'description']
    ordering_fields = ['price_monthly', 'price_annually', 'created_at']
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return PlanUpdateSerializer
        return PlanSerializer
    
    def perform_create(self, serializer):
        """Créer un plan et synchroniser avec Stripe si nécessaire"""
        plan = serializer.save()
        
        # Synchroniser avec Stripe si ce n'est pas un plan gratuit
        if plan.plan_type != 'decouverte' and plan.price_monthly > 0:
            try:
                StripeService.create_stripe_product_and_prices(plan)
            except Exception as e:
                # Journaliser l'erreur mais ne pas empêcher la création du plan
                print(f"Erreur lors de la création du produit Stripe: {str(e)}")
    
    def perform_update(self, serializer):
        """Mettre à jour un plan et synchroniser avec Stripe si nécessaire"""
        old_plan = self.get_object()
        plan = serializer.save()
        
        # Synchroniser avec Stripe si les prix ont changé
        if (plan.plan_type != 'decouverte' and 
            (old_plan.price_monthly != plan.price_monthly or 
             old_plan.price_annually != plan.price_annually)):
            try:
                StripeService.update_stripe_prices(plan)
            except Exception as e:
                print(f"Erreur lors de la mise à jour des prix Stripe: {str(e)}")

class SubscriptionAdminViewSet(viewsets.ModelViewSet):
    """Gestion complète des abonnements pour l'administration"""
    queryset = Subscription.objects.all().select_related('user', 'plan')
    serializer_class = SubscriptionAdminSerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'billing_cycle', 'plan__plan_type']
    search_fields = ['user__email', 'user__username', 'plan__name', 'stripe_customer_id']
    ordering_fields = ['start_date', 'current_period_end', 'created_at', 'updated_at']
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return SubscriptionUpdateSerializer
        return SubscriptionAdminSerializer
    
    def perform_create(self, serializer):
        """Créer un abonnement et synchroniser avec Stripe si nécessaire"""
        subscription = serializer.save()

        
        # Synchroniser avec Stripe si ce n'est pas un abonnement gratuit
        if subscription.plan.plan_type != 'decouverte' and subscription.plan.price_monthly > 0:
            try:
                # Créer un client Stripe si nécessaire
                if not subscription.stripe_customer_id:
                    customer_id = StripeService.create_customer(subscription.user)
                    subscription.stripe_customer_id = customer_id
                    subscription.save(update_fields=['stripe_customer_id'])
                
                # Créer l'abonnement Stripe
                StripeService.create_subscription(
                    subscription.user,
                    subscription.plan,
                    subscription.billing_cycle
                )
            except Exception as e:
                print(f"Erreur lors de la création de l'abonnement Stripe: {str(e)}")

class PaymentHistoryViewSet(viewsets.ModelViewSet):
    """Gestion complète de l'historique des paiements pour l'administration"""
    queryset = PaymentHistory.objects.all().select_related('subscription', 'subscription__user', 'subscription__plan')
    serializer_class = PaymentHistorySerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'subscription__plan__plan_type']
    search_fields = ['subscription__user__email', 'stripe_invoice_id', 'stripe_payment_intent_id']
    ordering_fields = ['payment_date', 'amount']

# ======= ADMIN DASHBOARD VIEWS =======

class SubscriptionStatsView(APIView):
    """Statistiques d'abonnement pour le tableau de bord d'administration"""
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Nombre total d'abonnements et par statut
        total_subscriptions = Subscription.objects.count()
        status_counts = Subscription.objects.values('status').annotate(count=Count('id'))
        
        # Répartition par plan
        plan_distribution = (
            Subscription.objects
            .values('plan__name', 'plan__plan_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Répartition par cycle de facturation
        billing_cycle_counts = Subscription.objects.values('billing_cycle').annotate(count=Count('id'))
        
        # Nombre de paiements réussis et montant total
        payment_stats = (
            PaymentHistory.objects
            .filter(status='paid')
            .aggregate(
                total_payments=Count('id'),
                total_amount=Sum('amount')
            )
        )
        
        # Statistiques d'utilisation globale
        usage_stats = {
            'total_signatures': Subscription.objects.aggregate(total=Sum('signatures_used'))['total'] or 0,
            'total_storage': Subscription.objects.aggregate(total=Sum('storage_used'))['total'] or 0,
        }
        
        # Abonnements proches de leur date de fin
        expiring_soon = (
            Subscription.objects
            .filter(
                status='active',
                current_period_end__lte=timezone.now() + timezone.timedelta(days=7)
            )
            .count()
        )
        
        return Response({
            'total_subscriptions': total_subscriptions,
            'status_counts': status_counts,
            'plan_distribution': plan_distribution,
            'billing_cycle_counts': billing_cycle_counts,
            'payment_stats': payment_stats,
            'usage_stats': usage_stats,
            'expiring_soon': expiring_soon
        })

# ======= ADMIN ACTIONS =======

@api_view(['POST'])
@permission_classes([IsAdminUser])
def sync_stripe_plans(request):
    """Synchroniser tous les plans avec Stripe"""
    plans = Plan.objects.filter(
        is_active=True, 
        plan_type__in=['professionnel', 'entreprise', 'gouvernement']
    )
    
    results = {'success': [], 'errors': []}
    
    for plan in plans:
        try:
            StripeService.create_stripe_product_and_prices(plan)
            results['success'].append(f"Plan {plan.name} synchronisé avec succès")
        except Exception as e:
            results['errors'].append(f"Erreur pour le plan {plan.name}: {str(e)}")
    
    return Response(results)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_usage_counters(request, subscription_id):
    """Réinitialiser les compteurs d'utilisation d'un abonnement"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    subscription.reset_usage_counters()
    
    return Response({
        'status': 'success',
        'message': f"Compteurs réinitialisés pour l'abonnement de {subscription.user.email}"
    })

@api_view(['POST'])
@permission_classes([IsAdminUser])
def extend_subscription_period(request, subscription_id):
    """Prolonger la période d'un abonnement"""
    subscription = get_object_or_404(Subscription, id=subscription_id)
    days = request.data.get('days', 30)
    
    try:
        days = int(days)
        if days <= 0:
            return Response(
                {'error': 'Le nombre de jours doit être positif'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except ValueError:
        return Response(
            {'error': 'Le nombre de jours doit être un entier'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Prolonger la période
    subscription.current_period_end = subscription.current_period_end + timezone.timedelta(days=days)
    subscription.save(update_fields=['current_period_end'])
    
    return Response({
        'status': 'success',
        'message': f"Période prolongée de {days} jours",
        'new_end_date': subscription.current_period_end
    })

# ======= EXISTING WEBHOOK & API VIEWS =======

@csrf_exempt
def stripe_webhook(request):
    """Point de terminaison pour les webhooks Stripe"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    print(f"==== WEBHOOK STRIPE REÇU: {request.method} ====")
    print(f"Signature header: {sig_header}")
    
    try:
        # Utiliser un try/except pour afficher plus d'informations en cas d'erreur
        print("Traitement du webhook...")
        result = StripeService.process_webhook_event(payload, sig_header)
        print(f"Résultat du traitement: {result}")
        
        if 'error' in result:
            print(f"ERREUR WEBHOOK: {result['error']}")
            return JsonResponse({'error': result['error']}, status=400)
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        print(f"EXCEPTION WEBHOOK: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def usage_stats(request):
    """Statistiques d'utilisation de l'abonnement pour l'interface Web"""
    try:
        subscription = request.user.subscription
        
        context = {
            'subscription': subscription,
            'signatures_used': subscription.signatures_used,
            'signatures_limit': subscription.plan.max_signatures,
            'signatures_remaining': subscription.remaining_signatures,
            'storage_used': subscription.storage_used,
            'storage_limit': subscription.plan.storage_limit,
            'storage_percent': (subscription.storage_used / subscription.plan.storage_limit * 100) 
                if subscription.plan.storage_limit > 0 else 0,
        }
        
        return render(request, 'subscriptions/usage.html', context)
        
    except Subscription.DoesNotExist:
        messages.error(request, "Vous n'avez pas d'abonnement actif")
        return redirect('subscription_dashboard')

# ======= FRONTEND API VIEWS =======

@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def plans_list_api(request):
    """API pour lister tous les plans disponibles"""
    plans = Plan.objects.filter(is_active=True).order_by('price_monthly')
    plans_data = [
        {
            'id': plan.id,
            'name': plan.name,
            'plan_type': plan.plan_type,
            'description': plan.description,
            'price_monthly': float(plan.price_monthly),
            'price_annually': float(plan.price_annually),
            'max_signatures': plan.max_signatures,
            'max_signers': plan.max_signers,
            'storage_limit': plan.storage_limit,
            'retention_days': plan.retention_days,
            'has_api_access': plan.has_api_access,
            'support_level': plan.support_level,
            'is_active': plan.is_active,
        }
        for plan in plans
    ]
    return Response(PlanSerializer(plans_data, many=True).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_subscription_api(request):
    """API pour obtenir l'abonnement actuel de l'utilisateur"""
    try:
        # Récupérer le dernier abonnement actif de l'utilisateur
        subscription = request.user.subscriptions.filter(status='active').order_by('-created_at').first()
        
        # Si l'utilisateur n'a pas d'abonnement, créer un abonnement par défaut au plan gratuit
        if not subscription:
            free_plan = Plan.objects.get(plan_type='decouverte')
            subscription = Subscription.objects.create(
                user=request.user,
                plan=free_plan,
                status='active',
                start_date=timezone.now(),
                current_period_end=timezone.now() + timezone.timedelta(days=30),
                billing_cycle='monthly'
            )
        
        # Construire la réponse
        response_data = {
            'id': subscription.id,
            'user': request.user.email,
            'plan': {
                'id': subscription.plan.id,
                'name': subscription.plan.name,
                'plan_type': subscription.plan.plan_type,
                'description': subscription.plan.description,
                'price_monthly': float(subscription.plan.price_monthly),
                'price_annually': float(subscription.plan.price_annually),
                'max_signatures': subscription.plan.max_signatures,
                'max_signers': subscription.plan.max_signers,
                'storage_limit': subscription.plan.storage_limit,
                'retention_days': subscription.plan.retention_days,
                'has_api_access': subscription.plan.has_api_access,
                'support_level': subscription.plan.support_level,
            },
            'status': subscription.status,
            'billing_cycle': subscription.billing_cycle,
            'start_date': subscription.start_date.isoformat(),
            'current_period_end': subscription.current_period_end.isoformat(),
            'canceled_at': subscription.canceled_at.isoformat() if subscription.canceled_at else None,
            'signatures_used': subscription.signatures_used,
            'storage_used': subscription.storage_used,
            'remaining_signatures': subscription.remaining_signatures,
        }
        
        return Response(response_data)
    except Subscription.DoesNotExist:
        # Créer un abonnement par défaut
        free_plan = Plan.objects.get(plan_type='decouverte')
        subscription = Subscription.objects.create(
            user=request.user,
            plan=free_plan,
            status='active',
            start_date=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
            billing_cycle='monthly'
        )
    
        
        # Récupérer les données de l'abonnement nouvellement créé
        response_data = {
            'id': subscription.id,
            'user': request.user.email,
            'plan': {
                'id': subscription.plan.id,
                'name': subscription.plan.name,
                'plan_type': subscription.plan.plan_type,
                'description': subscription.plan.description,
                'price_monthly': float(subscription.plan.price_monthly),
                'price_annually': float(subscription.plan.price_annually),
                'max_signatures': subscription.plan.max_signatures,
                'max_signers': subscription.plan.max_signers,
                'storage_limit': subscription.plan.storage_limit,
                'retention_days': subscription.plan.retention_days,
                'has_api_access': subscription.plan.has_api_access,
                'support_level': subscription.plan.support_level,
            },
            'status': subscription.status,
            'billing_cycle': subscription.billing_cycle,
            'start_date': subscription.start_date.isoformat(),
            'current_period_end': subscription.current_period_end.isoformat(),
            'canceled_at': subscription.canceled_at.isoformat() if subscription.canceled_at else None,
            'signatures_used': subscription.signatures_used,
            'storage_used': subscription.storage_used,
            'remaining_signatures': subscription.remaining_signatures,
        }
        
        return Response(response_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_plan_api(request, plan_id):
    """API pour changer de plan d'abonnement"""
    plan = get_object_or_404(Plan, id=plan_id, is_active=True)
    billing_cycle = request.data.get('billing_cycle', 'monthly')
    
    # Si le plan est gratuit, passer directement au forfait gratuit
    if plan.plan_type == 'decouverte':
        try:
            subscription = request.user.subscriptions
            
            # Si l'utilisateur a un abonnement payant, l'annuler d'abord
            if subscription.plan.price_monthly > 0 and subscription.stripe_subscription_id:
                StripeService.cancel_subscription(subscription)
                return Response ({'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                
                
            
            # Mettre à jour l'abonnement
            subscription.plan = plan
            subscription.status = 'active'
            subscription.billing_cycle = 'monthly'  # Le forfait gratuit est toujours mensuel
            subscription.start_date = timezone.now()
            subscription.current_period_end = timezone.now() + timezone.timedelta(days=30)
            subscription.save()
            
            return Response({'status': 'success', 'message': 'Forfait mis à jour avec succès'})
            
        except Subscription.DoesNotExist:
            # Créer un nouvel abonnement gratuit
            Subscription.objects.create(
                user=request.user,
                plan=plan,
                status='active',
                start_date=timezone.now(),
                current_period_end=timezone.now() + timezone.timedelta(days=30),
                billing_cycle='monthly'
                
            )
            return Response({'status': 'success', 'message': 'Inscription au forfait gratuit réussie'})
    
    # Pour les plans payants, créer une session de paiement
    try:
        # Vérifier si l'utilisateur a déjà un abonnement
        try:
            subscription = request.user.subscriptions
            
            # Créer la session de paiement pour la mise à jour
            checkout_result = StripeService.create_checkout_session(
                user=request.user,
                plan=plan,
                billing_cycle=billing_cycle,
                subscription=subscription
            )
            
            # Vérifier si le résultat est une session ou simplement une URL (pour les plans gratuits)
            if isinstance(checkout_result, dict) and 'url' in checkout_result:
                return Response({'checkout_url': checkout_result['url']})
            else:
                return Response({'checkout_url': checkout_result.url})
            
        except Subscription.DoesNotExist:
            # Créer un client Stripe si nécessaire
            customer_id = StripeService.create_customer(request.user)
            
            # Créer une session de paiement
            checkout_result = StripeService.create_checkout_session(
                user=request.user,
                plan=plan,
                billing_cycle=billing_cycle
            )
            
            # Vérifier si le résultat est une session ou simplement une URL
            if isinstance(checkout_result, dict) and 'url' in checkout_result:
                return Response({'checkout_url': checkout_result['url']})
            else:
                return Response({'checkout_url': checkout_result.url})
            
    except Exception as e:
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_subscription_api(request):
    """API pour annuler un abonnement"""
    try:
        subscription = request.user.subscription
        StripeService.cancel_subscription(subscription)
        
        return Response({
            'status': 'success',
            'message': 'Abonnement annulé avec succès'
        })
        
    except Subscription.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Aucun abonnement actif trouvé'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def usage_stats_api(request):
    """API pour obtenir les statistiques d'utilisation"""
    try:
        subscription = request.user.subscriptions.filter(status='active').order_by('-created_at').first()
        
        response_data = {
            'signatures_used': subscription.signatures_used,
            'signatures_limit': subscription.plan.max_signatures,
            'signatures_remaining': subscription.remaining_signatures,
            'storage_used': subscription.storage_used,
            'storage_limit': subscription.plan.storage_limit,
            'storage_percent': (subscription.storage_used / subscription.plan.storage_limit * 100)
            if subscription.plan.storage_limit > 0 else 0,
        }
        
        return Response(response_data)
        
    except Subscription.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Aucun abonnement actif trouvé'},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def paydunya_checkout_api(request, plan_id):
    """Crée une demande de paiement mobile money via PayDunya"""
    try:
        # Récupérer le plan
        plan = get_object_or_404(Plan, id=plan_id, is_active=True)
        
        # Récupérer ou créer un abonnement pour l'utilisateur
        try:
            # Vérifier si l'utilisateur a déjà des abonnements
            user_subscriptions = Subscription.objects.filter(user=request.user)
            
            if user_subscriptions.exists():
                # Utiliser le premier abonnement actif, ou le premier abonnement trouvé s'il n'y a pas d'abonnement actif
                subscription = user_subscriptions.filter(status='active').first() or user_subscriptions.first()
                
                # Mise à jour du plan et du cycle de facturation
                subscription.plan = plan
                subscription.billing_cycle = request.data.get('billing_cycle', subscription.billing_cycle)
                subscription.save()
            else:
                # Créer un nouvel abonnement si aucun n'existe
                subscription = Subscription.objects.create(
                    user=request.user,
                    plan=plan,
                    status='pending',
                    billing_cycle=request.data.get('billing_cycle', 'monthly')
                )
        except Exception as e:
            return Response({
                'success': False,
                'message': f"Erreur lors de la récupération/création de l'abonnement: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Créer la demande de paiement PayDunya
        payment_response = PayDunyaService.create_payment_request(
            subscription=subscription,
            plan=plan,
            billing_cycle=subscription.billing_cycle
        )
        
        if not payment_response.get('success'):
            return Response({
                'success': False,
                'message': payment_response.get('error', 'Une erreur est survenue lors de la création de la demande de paiement')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Retourner l'URL de redirection et autres informations
        return Response({
            'success': True,
            'checkout_url': payment_response.get('checkout_url'),
            'token': payment_response.get('token')
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def paydunya_webhook(request):
    """Webhook pour les notifications de paiement PayDunya"""
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    try:
        # Récupérer le payload
        payload = json.loads(request.body)
        
        # Traiter l'événement
        success = PayDunyaService.process_webhook_event(payload)
        
        if success:
            return HttpResponse(status=200)
        else:
            return HttpResponse(status=400)
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement du webhook PayDunya: {str(e)}")
        return HttpResponse(status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_payment_status_api(request, token):
    """Vérifie le statut d'un paiement PayDunya"""
    try:
        # Vérifier le statut du paiement
        payment_status = PayDunyaService.check_payment_status(token)
        
        if not payment_status.get('success'):
            return Response({
                'success': False,
                'message': payment_status.get('error', 'Une erreur est survenue lors de la vérification du paiement')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Retourner le statut
        return Response({
            'success': True,
            'status': payment_status.get('status'),
            'data': payment_status.get('data')
        })
    
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def debug_plans_api(request):
    """Vue de débogage pour afficher tous les plans existants"""
    plans = Plan.objects.all()
    plans_data = []
    
    for plan in plans:
        plans_data.append({
            'id': plan.id,
            'name': plan.name,
            'plan_type': plan.plan_type,
            'price_monthly': float(plan.price_monthly),
            'price_annually': float(plan.price_annually),
            'is_active': plan.is_active
        })
    
    # Si aucun plan n'existe, en créer un
    if not plans_data:
        test_plan = Plan.objects.create(
            name="Plan de test",
            plan_type="decouverte",
            description="Plan créé pour tester PayDunya",
            price_monthly=2500,
            price_annually=25000,
            max_signatures=10,
            max_signers=2,
            storage_limit=100,
            is_active=True
        )
        
        plans_data.append({
            'id': test_plan.id,
            'name': test_plan.name,
            'plan_type': test_plan.plan_type,
            'price_monthly': float(test_plan.price_monthly),
            'price_annually': float(test_plan.price_annually),
            'is_active': test_plan.is_active,
            'created': True
        })
    
    return Response({
        'count': len(plans_data),
        'plans': plans_data
    })

@api_view(['GET'])
def paydunya_error_view(request):
    """Vue pour afficher les erreurs PayDunya de manière conviviale"""
    error_message = request.GET.get('message', "Une erreur s'est produite lors du traitement de votre paiement PayDunya.")
    error_code = request.GET.get('code', '')
    support_email = getattr(settings, 'SUPPORT_EMAIL', 'support@wolofsign.com')
    
    return render(request, 'subscriptions/paydunya_error.html', {
        'error_message': error_message,
        'error_code': error_code,
        'support_email': support_email
    })