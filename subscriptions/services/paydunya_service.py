import requests
import json
import logging
from django.conf import settings
from django.utils import timezone
from ..models import Subscription, PaymentHistory, Plan

# Configuration du logger
logger = logging.getLogger(__name__)

class PayDunyaService:
    """
    Service pour gérer les paiements via PayDunya Mobile Money
    Documentation: https://developers.paydunya.com/
    """
    
    # URL de base de l'API PayDunya (à configurer dans settings.py)
    BASE_URL = getattr(settings, 'PAYDUNYA_BASE_URL', 'https://app.paydunya.com/api/v1')
    MASTER_KEY = getattr(settings, 'PAYDUNYA_MASTER_KEY', '')
    PRIVATE_KEY = getattr(settings, 'PAYDUNYA_PRIVATE_KEY', '')
    PUBLIC_KEY = getattr(settings, 'PAYDUNYA_PUBLIC_KEY', '') 
    TOKEN = getattr(settings, 'PAYDUNYA_TOKEN', '')
    
    # Paramètres pour le mode test vs production
    IS_TEST_MODE = getattr(settings, 'PAYDUNYA_TEST_MODE', True)
    
    @classmethod
    def get_headers(cls):
        """Retourne les en-têtes d'authentification pour l'API PayDunya"""
        return {
            'PAYDUNYA-MASTER-KEY': cls.MASTER_KEY,
            'PAYDUNYA-PRIVATE-KEY': cls.PRIVATE_KEY,
            'PAYDUNYA-PUBLIC-KEY': cls.PUBLIC_KEY,
            'PAYDUNYA-TOKEN': cls.TOKEN,
            'Content-Type': 'application/json'
        }
    
    @classmethod
    def create_payment_request(cls, subscription, plan, billing_cycle='monthly'):
        """
        Crée une demande de paiement Mobile Money via PayDunya
        
        Args:
            subscription: L'objet Subscription
            plan: L'objet Plan
            billing_cycle: 'monthly' ou 'annually'
            
        Returns:
            dict: Informations sur la demande de paiement, notamment l'URL de redirection
        """
        try:
            # Vérifier si les clés PayDunya sont configurées
            if not all([cls.MASTER_KEY, cls.PRIVATE_KEY, cls.PUBLIC_KEY, cls.TOKEN]):
                logger.error("Les clés PayDunya ne sont pas toutes configurées")
                return {
                    'success': False,
                    'error': "Les clés PayDunya ne sont pas toutes configurées. Veuillez configurer PAYDUNYA_MASTER_KEY, PAYDUNYA_PRIVATE_KEY, PAYDUNYA_PUBLIC_KEY et PAYDUNYA_TOKEN."
                }
            
            user = subscription.user
            
            # Déterminer le montant en fonction du cycle de facturation
            amount = plan.price_monthly if billing_cycle == 'monthly' else plan.price_annually
            
            # Préparer les données pour la demande de paiement
            payload = {
                "invoice": {
                    "items": {
                        "item_0": {
                            "name": f"Abonnement {plan.name} ({billing_cycle})",
                            "quantity": 1,
                            "unit_price": str(amount),
                            "total_price": str(amount),
                            "description": f"Abonnement {billing_cycle} au plan {plan.name}"
                        }
                    },
                    "total_amount": str(amount),
                    "description": f"Paiement d'abonnement - Plan {plan.name} - {billing_cycle}"
                },
                "store": {
                    "name": getattr(settings, 'STORE_NAME', "Wolof Sign"),
                    "tagline": getattr(settings, 'STORE_TAGLINE', "Signature électronique en toute simplicité"),
                    "phone": getattr(settings, 'STORE_PHONE', '+221 XX XXX XX XX'),
                    "postal_address": getattr(settings, 'STORE_ADDRESS', 'Dakar, Sénégal'),
                    "website_url": getattr(settings, 'SITE_URL', 'http://localhost:8000')
                },
                "custom_data": {
                    "user_id": str(user.id),
                    "subscription_id": str(subscription.id),
                    "plan_id": str(plan.id),
                    "billing_cycle": billing_cycle
                },
                "actions": {
                    "cancel_url": getattr(settings, 'PAYDUNYA_CANCEL_URL', settings.STRIPE_CANCEL_URL),
                    "return_url": getattr(settings, 'PAYDUNYA_SUCCESS_URL', settings.STRIPE_SUCCESS_URL),
                    "callback_url": f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/api/subscriptions/webhook/paydunya/"
                }
            }
            
            # Ajouter les informations du client si disponibles
            if user.first_name or user.last_name:
                payload["customer"] = {
                    "name": f"{user.first_name} {user.last_name}".strip(),
                    "email": user.email
                }
            
            # Log des données envoyées à PayDunya
            logger.debug(f"Envoi de la requête à PayDunya: {json.dumps(payload, indent=2)}")
            logger.debug(f"En-têtes: {cls.get_headers()}")
            
            # Appel à l'API PayDunya pour créer la demande de paiement
            response = requests.post(
                f"{cls.BASE_URL}/checkout-invoice/create",
                headers=cls.get_headers(),
                json=payload
            )
            
            # Vérifier la réponse
            response_data = response.json()
            logger.debug(f"Réponse de PayDunya: {json.dumps(response_data, indent=2)}")
            
            if response.status_code != 200 or not response_data.get('response_code') == '00':
                error_message = f"Erreur lors de la création de la demande de paiement PayDunya: {response_data}"
                logger.error(error_message)
                
                # Si les clés d'API ne sont pas valides ou si le compte n'est pas activé
                if response_data.get('response_code') == '1001':
                    error_message = "Votre compte PayDunya n'est pas complètement activé. Veuillez vous connecter à votre compte PayDunya et terminer l'activation."
                
                raise Exception(f"Erreur PayDunya: {response_data.get('response_text', 'Erreur inconnue')}")
            
            # Créer un enregistrement dans l'historique des paiements
            payment = PaymentHistory.objects.create(
                subscription=subscription,
                amount=amount,
                status='pending',
                payment_method='mobile_money',
                paydunya_token=response_data.get('token')
            )
            
            # Retourner les informations nécessaires pour rediriger l'utilisateur
            return {
                'success': True,
                'token': response_data.get('token'),
                'checkout_url': response_data.get('response_text'),
                'payment_id': payment.id
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la demande de paiement PayDunya: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def check_payment_status(cls, token):
        """
        Vérifie le statut d'un paiement PayDunya
        
        Args:
            token: Le token PayDunya à vérifier
            
        Returns:
            dict: Informations sur le statut du paiement
        """
        try:
            # Vérifier si les clés PayDunya sont configurées
            if not all([cls.MASTER_KEY, cls.PRIVATE_KEY, cls.PUBLIC_KEY, cls.TOKEN]):
                logger.error("Les clés PayDunya ne sont pas toutes configurées")
                return {
                    'success': False,
                    'error': "Les clés PayDunya ne sont pas toutes configurées."
                }
            
            response = requests.get(
                f"{cls.BASE_URL}/checkout-invoice/confirm/{token}",
                headers=cls.get_headers()
            )
            
            response_data = response.json()
            logger.debug(f"Réponse de vérification PayDunya: {json.dumps(response_data, indent=2)}")
            
            if response.status_code != 200:
                logger.error(f"Erreur lors de la vérification du paiement PayDunya: {response_data}")
                return {
                    'success': False,
                    'error': f"Erreur PayDunya: {response_data.get('response_text', 'Erreur inconnue')}"
                }
            
            return {
                'success': True,
                'status': response_data.get('status'),
                'data': response_data
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du paiement PayDunya: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @classmethod
    def process_webhook_event(cls, payload):
        """
        Traite les événements de webhook PayDunya
        
        Args:
            payload: Les données du webhook
            
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        try:
            logger.debug(f"Traitement du webhook PayDunya: {json.dumps(payload, indent=2)}")
            
            # Vérifier si c'est un paiement confirmé
            if payload.get('status') != 'completed':
                logger.info(f"Webhook PayDunya - Statut non traité: {payload.get('status')}")
                return True  # On considère comme traité même si on ne fait rien
            
            # Récupérer le token et les données personnalisées
            token = payload.get('token')
            if not token:
                logger.error("Webhook PayDunya - Aucun token trouvé dans la payload")
                return False
            
            # Vérifier le paiement
            custom_data = payload.get('custom_data', {})
            user_id = custom_data.get('user_id')
            subscription_id = custom_data.get('subscription_id')
            plan_id = custom_data.get('plan_id')
            billing_cycle = custom_data.get('billing_cycle', 'monthly')
            
            logger.debug(f"Données personnalisées du webhook: {custom_data}")
            
            if not all([user_id, subscription_id, plan_id]):
                logger.error(f"Webhook PayDunya - Données personnalisées incomplètes: {custom_data}")
                return False
            
            # Trouver le paiement en attente correspondant
            try:
                payment = PaymentHistory.objects.get(paydunya_token=token, status='pending')
                logger.info(f"Paiement trouvé: {payment.id}")
            except PaymentHistory.DoesNotExist:
                logger.error(f"Webhook PayDunya - Aucun paiement trouvé pour le token: {token}")
                return False
            
            # Mettre à jour le statut du paiement
            payment.status = 'paid'
            payment.save()
            logger.info(f"Statut du paiement mis à jour: {payment.id} -> paid")
            
            # Mettre à jour l'abonnement
            subscription = payment.subscription
            subscription.status = 'active'
            
            # Définir la période d'abonnement
            subscription.start_date = timezone.now()
            if billing_cycle == 'monthly':
                subscription.current_period_end = timezone.now() + timezone.timedelta(days=30)
            else:
                subscription.current_period_end = timezone.now() + timezone.timedelta(days=365)
            
            subscription.save()
            logger.info(f"Abonnement mis à jour: {subscription.id} -> active")
            
            logger.info(f"Webhook PayDunya - Paiement {token} traité avec succès")
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Erreur lors du traitement du webhook PayDunya: {str(e)}")
            logger.error(traceback.format_exc())
            return False 