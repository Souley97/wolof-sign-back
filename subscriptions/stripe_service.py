import stripe
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging
from .models import Plan, Subscription, PaymentHistory

# Configuration du logger
logger = logging.getLogger(__name__)

# Configuration Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
SITE_URL = getattr(settings, 'SITE_URL', 'http://localhost:8000')

class StripeService:
    @staticmethod
    def create_customer(user):
        """Crée un client Stripe pour un utilisateur"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip() or user.username,
                metadata={"user_id": str(user.id)},
                description=f"Utilisateur {user.username} de Wolof Sign"
            )
            logger.info(f"Client Stripe créé pour l'utilisateur {user.email}: {customer.id}")
            return customer.id
        except Exception as e:
            logger.error(f"Erreur lors de la création du client Stripe: {str(e)}")
            raise
    
    @staticmethod
    def create_stripe_product_and_prices(plan):
        """Crée ou met à jour un produit et ses prix dans Stripe"""
        try:
            # Vérifier si le produit existe déjà par metadata plan_id
            existing_products = stripe.Product.list(
                limit=1,
                active=True,
                metadata={"plan_id": str(plan.id)}
            )
            
            if existing_products and existing_products.data:
                product = existing_products.data[0]
                logger.info(f"Produit Stripe existant trouvé pour le plan {plan.name}: {product.id}")
            else:
                # Créer un nouveau produit
                product = stripe.Product.create(
                    name=plan.name,
                    description=plan.description,
                    metadata={
                        "plan_id": str(plan.id),
                        "plan_type": plan.plan_type
                    }
                )
                logger.info(f"Nouveau produit Stripe créé pour le plan {plan.name}: {product.id}")
            
            # Créer les prix si nécessaire
            if not plan.stripe_price_id_monthly:
                price_monthly = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(plan.price_monthly ),  # En centimes
                    currency='xof',  # Franc CFA
                    recurring={"interval": "month"},
                    metadata={
                        "plan_id": str(plan.id),
                        "billing_cycle": "monthly"
                    }
                )
                plan.stripe_price_id_monthly = price_monthly.id
                logger.info(f"Prix mensuel Stripe créé pour le plan {plan.name}: {price_monthly.id}")
            
            if not plan.stripe_price_id_annually:
                price_annually = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(plan.price_annually ),  # En centimes
                    currency='xof',  # Franc CFA
                    recurring={"interval": "year"},
                    metadata={
                        "plan_id": str(plan.id),
                        "billing_cycle": "annually"
                    }
                )
                plan.stripe_price_id_annually = price_annually.id
                logger.info(f"Prix annuel Stripe créé pour le plan {plan.name}: {price_annually.id}")
            
            # Sauvegarder les IDs Stripe
            plan.save(update_fields=['stripe_price_id_monthly', 'stripe_price_id_annually'])
            
            return {
                "product_id": product.id,
                "price_monthly_id": plan.stripe_price_id_monthly,
                "price_annually_id": plan.stripe_price_id_annually
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la création/mise à jour du produit Stripe: {str(e)}")
            raise
    
    @staticmethod
    def update_stripe_prices(plan):
        """Met à jour les prix d'un plan existant dans Stripe"""
        try:
            # Pour Stripe, on ne peut pas modifier les prix existants
            # Au lieu de cela, on crée de nouveaux prix et on archive les anciens
            
            # Récupérer le produit
            existing_products = stripe.Product.list(
                limit=1,
                active=True,
                metadata={"plan_id": str(plan.id)}
            )
            
            if not existing_products or not existing_products.data:
                # Si le produit n'existe pas, créer tout de nouveau
                return StripeService.create_stripe_product_and_prices(plan)
            
            product = existing_products.data[0]
            
            # Archiver les anciens prix (optionnel)
            if plan.stripe_price_id_monthly:
                try:
                    stripe.Price.modify(
                        plan.stripe_price_id_monthly,
                        active=False
                    )
                    logger.info(f"Prix mensuel archivé: {plan.stripe_price_id_monthly}")
                except Exception as e:
                    logger.warning(f"Erreur lors de l'archivage du prix mensuel: {str(e)}")
            
            if plan.stripe_price_id_annually:
                try:
                    stripe.Price.modify(
                        plan.stripe_price_id_annually,
                        active=False
                    )
                    logger.info(f"Prix annuel archivé: {plan.stripe_price_id_annually}")
                except Exception as e:
                    logger.warning(f"Erreur lors de l'archivage du prix annuel: {str(e)}")
            
            # Créer de nouveaux prix
            price_monthly = stripe.Price.create(
                product=product.id,
                unit_amount=int(plan.price_monthly ),  # En centimes
                currency='xof',  # Franc CFA
                recurring={"interval": "month"},
                metadata={
                    "plan_id": str(plan.id),
                    "billing_cycle": "monthly"
                }
            )
            
            price_annually = stripe.Price.create(
                product=product.id,
                unit_amount=int(plan.price_annually ),  # En centimes
                currency='xof',  # Franc CFA
                recurring={"interval": "year"},
                metadata={
                    "plan_id": str(plan.id),
                    "billing_cycle": "annually"
                }
            )
            
            # Mettre à jour les IDs dans le modèle
            plan.stripe_price_id_monthly = price_monthly.id
            plan.stripe_price_id_annually = price_annually.id
            plan.save(update_fields=['stripe_price_id_monthly', 'stripe_price_id_annually'])
            
            logger.info(f"Nouveaux prix créés pour le plan {plan.name}: {price_monthly.id}, {price_annually.id}")
            
            return {
                "product_id": product.id,
                "price_monthly_id": price_monthly.id,
                "price_annually_id": price_annually.id
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des prix Stripe: {str(e)}")
            raise
    
    @staticmethod
    def create_subscription(user, plan, billing_cycle='monthly'):
        """Crée un abonnement Stripe"""
        try:
            # S'assurer que l'utilisateur a un ID client
            if not user.subscription.stripe_customer_id:
                customer_id = StripeService.create_customer(user)
                user.subscription.stripe_customer_id = customer_id
                user.subscription.save(update_fields=['stripe_customer_id'])
            
            # Déterminer le prix Stripe à utiliser
            price_id = plan.stripe_price_id_monthly if billing_cycle == 'monthly' else plan.stripe_price_id_annually
            
            if not price_id:
                # Si le prix n'existe pas, synchroniser avec Stripe
                stripe_info = StripeService.create_stripe_product_and_prices(plan)
                price_id = stripe_info["price_monthly_id"] if billing_cycle == 'monthly' else stripe_info["price_annually_id"]
            
            # Créer l'abonnement dans Stripe
            subscription = stripe.Subscription.create(
                customer=user.subscription.stripe_customer_id,
                items=[{"price": price_id}],
                metadata={
                    "user_id": str(user.id),
                    "plan_id": str(plan.id),
                    "billing_cycle": billing_cycle
                }
            )
            
            # Mettre à jour ou créer l'objet Subscription
            end_date = timezone.now() + timedelta(days=30 if billing_cycle == 'monthly' else 365)
            
            user_subscription = Subscription.objects.get(user=user)
            user_subscription.plan = plan
            user_subscription.status = subscription.status
            user_subscription.stripe_subscription_id = subscription.id
            user_subscription.billing_cycle = billing_cycle
            user_subscription.start_date = timezone.now()
            user_subscription.current_period_end = end_date
            user_subscription.save()
            
            logger.info(f"Abonnement Stripe créé: {subscription.id} pour {user.email}")
            return user_subscription
        
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'abonnement Stripe: {str(e)}")
            raise
    
    @staticmethod
    def cancel_subscription(subscription):
        """Annule un abonnement"""
        try:
            if subscription.stripe_subscription_id:
                stripe.Subscription.delete(subscription.stripe_subscription_id)
                logger.info(f"Abonnement Stripe annulé: {subscription.stripe_subscription_id}")
                
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
            subscription.save(update_fields=['status', 'canceled_at'])
            
            return subscription
        
        except Exception as e:
            logger.error(f"Erreur lors de l'annulation de l'abonnement: {str(e)}")
            raise
    
    @staticmethod
    def update_subscription(subscription, new_plan, new_billing_cycle=None):
        """Met à jour un abonnement vers un nouveau plan"""
        try:
            if not new_billing_cycle:
                new_billing_cycle = subscription.billing_cycle
                
            # Déterminer le prix Stripe à utiliser
            price_id = new_plan.stripe_price_id_monthly if new_billing_cycle == 'monthly' else new_plan.stripe_price_id_annually
            
            if not price_id:
                # Si le prix n'existe pas, synchroniser avec Stripe
                stripe_info = StripeService.create_stripe_product_and_prices(new_plan)
                price_id = stripe_info["price_monthly_id"] if new_billing_cycle == 'monthly' else stripe_info["price_annually_id"]
            
            # Mettre à jour l'abonnement dans Stripe
            if subscription.stripe_subscription_id:
                stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[{
                        'id': stripe_subscription['items']['data'][0].id,
                        'price': price_id,
                    }],
                    metadata={
                        "user_id": str(subscription.user.id),
                        "plan_id": str(new_plan.id),
                        "billing_cycle": new_billing_cycle
                    }
                )
                logger.info(f"Abonnement Stripe mis à jour: {subscription.stripe_subscription_id}")
            
            # Mettre à jour l'objet Subscription local
            subscription.plan = new_plan
            subscription.billing_cycle = new_billing_cycle
            subscription.save(update_fields=['plan', 'billing_cycle'])
            
            return subscription
        
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'abonnement: {str(e)}")
            raise
    
    @classmethod
    def create_checkout_session(cls, user, plan, billing_cycle='monthly', subscription=None, return_session=False):
        """
        Crée une session de paiement Stripe.
        
        Args:
            user: L'utilisateur pour lequel créer la session
            plan: Le plan d'abonnement à utiliser
            billing_cycle: Le cycle de facturation ('monthly' ou 'annually')
            subscription: L'abonnement existant à mettre à jour (optionnel)
            return_session: Si True, renvoie la session complète au lieu de l'URL seule
            
        Returns:
            L'URL de checkout ou l'objet session complet
        """
        stripe.api_key = settings.STRIPE_SECRET_KEY
        logger = logging.getLogger('stripe')
        
        try:
            # Récupérer ou créer l'ID client Stripe
            customer_id = cls.get_stripe_customer_id(user)
            
            # Récupérer l'URL de succès et d'annulation depuis les settings
            success_url = settings.STRIPE_SUCCESS_URL
            cancel_url = settings.STRIPE_CANCEL_URL
            
            # Déterminer le prix à utiliser en fonction du cycle de facturation
            if billing_cycle == 'monthly':
                stripe_price_id = plan.stripe_price_id_monthly
            else:
                stripe_price_id = plan.stripe_price_id_annually
            
            # Vérifier que l'ID de prix existe
            if not stripe_price_id or not isinstance(stripe_price_id, str) or not stripe_price_id.startswith('price_'):
                raise ValueError(f"Aucun ID de prix Stripe valide trouvé pour le plan {plan.name} ({plan.id}) avec cycle {billing_cycle}. "
                              f"ID actuel: {stripe_price_id}")
            
            # Construire les options de session
            session_options = {
                'payment_method_types': ['card'],
                'line_items': [
                    {
                        'price': stripe_price_id,
                        'quantity': 1,
                    },
                ],
                'mode': 'subscription',
                'success_url': success_url,
                'cancel_url': cancel_url,
                'metadata': {
                    'user_id': str(user.id),
                    'plan_id': str(plan.id),
                    'billing_cycle': billing_cycle
                },
                'allow_promotion_codes': True,
            }
            
            # Ajouter l'ID client s'il existe
            if customer_id:
                session_options['customer'] = customer_id
            else:
                # Création automatique d'un client
                session_options['customer_email'] = user.email
            
            # Créer la session
            checkout_session = stripe.checkout.Session.create(**session_options)
            logger.info(f"Session de paiement Stripe créée: {checkout_session.id} pour {user.email}")
            
            return checkout_session
        
        except Exception as e:
            logger.error(f"Erreur lors de la création de la session de paiement: {str(e)}")
            raise
    
    @staticmethod
    def process_webhook_event(payload, signature):
        """Traite les événements webhook de Stripe"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )
            logger.info(f"Événement webhook Stripe reçu: {event['type']}")
        except ValueError as e:
            # Payload invalide
            logger.error(f"Webhook invalide: {str(e)}")
            return {"error": str(e)}
        except stripe.error.SignatureVerificationError as e:
            # Signature invalide
            logger.error(f"Signature webhook invalide: {str(e)}")
            return {"error": str(e)}
        
        # Traiter différents types d'événements
        if event['type'] == 'invoice.paid':
            StripeService._handle_successful_payment(event)
        elif event['type'] == 'customer.subscription.updated':
            StripeService._handle_subscription_updated(event)
        elif event['type'] == 'customer.subscription.deleted':
            StripeService._handle_subscription_canceled(event)
        elif event['type'] == 'checkout.session.completed':
            StripeService._handle_checkout_completed(event)
        
        return {"status": "success"}
    
    @staticmethod
    def _handle_successful_payment(event):
        """Gère un paiement réussi"""
        try:
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            
            if not subscription_id:
                logger.warning("Invoice sans ID d'abonnement")
                return
            
            subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if not subscription:
                logger.warning(f"Abonnement non trouvé: {subscription_id}")
                return
            
            # Créer l'entrée dans l'historique des paiements
            PaymentHistory.objects.create(
                subscription=subscription,
                amount=invoice.get('amount_paid') / 100,  # Conversion des centimes en FCFA
                payment_date=timezone.now(),
                stripe_invoice_id=invoice.get('id'),
                stripe_payment_intent_id=invoice.get('payment_intent', ''),
                status='paid',
                payment_method=invoice.get('payment_method_details', {}).get('type', 'card')
            )
            
            # Mise à jour de la date de fin de période
            if subscription.billing_cycle == 'monthly':
                subscription.current_period_end = timezone.now() + timedelta(days=30)
            else:
                subscription.current_period_end = timezone.now() + timedelta(days=365)
            
            # Réinitialiser les compteurs d'utilisation
            subscription.reset_usage_counters()
            subscription.save()
            
            logger.info(f"Paiement traité pour l'abonnement {subscription_id}")
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement du paiement: {str(e)}")
    
    @staticmethod
    def _handle_subscription_updated(event):
        """Gère la mise à jour d'un abonnement"""
        try:
            subscription_data = event['data']['object']
            subscription_id = subscription_data.get('id')
            
            subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if not subscription:
                logger.warning(f"Abonnement non trouvé: {subscription_id}")
                return
            
            subscription.status = subscription_data.get('status')
            
            if subscription_data.get('canceled_at'):
                subscription.canceled_at = timezone.datetime.fromtimestamp(
                    subscription_data.get('canceled_at'), tz=timezone.utc
                )
            
            subscription.save()
            logger.info(f"Abonnement mis à jour: {subscription_id}, statut: {subscription.status}")
        
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'abonnement: {str(e)}")
    
    @staticmethod
    def _handle_subscription_canceled(event):
        """Gère l'annulation d'un abonnement"""
        try:
            subscription_data = event['data']['object']
            subscription_id = subscription_data.get('id')
            
            subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if not subscription:
                logger.warning(f"Abonnement non trouvé: {subscription_id}")
                return
            
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
            subscription.save()
            
            logger.info(f"Abonnement annulé: {subscription_id}")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'annulation de l'abonnement: {str(e)}")
    
    @staticmethod
    def _handle_checkout_completed(event):
        """Gère une session de paiement Stripe Checkout complétée"""
        try:
            session = event['data']['object']
            logger.info(f"Traitement de la session de paiement: {session.id}")
            
            # Récupérer les métadonnées
            user_id = session.get('metadata', {}).get('user_id')
            plan_id = session.get('metadata', {}).get('plan_id')
            billing_cycle = session.get('metadata', {}).get('billing_cycle', 'monthly')
            customer_id = session.get('customer')
            
            if not user_id or not plan_id:
                logger.warning(f"Métadonnées manquantes dans la session: {session.id}")
                return
            
            # Récupérer l'utilisateur et le plan
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                user = User.objects.get(id=user_id)
                plan = Plan.objects.get(id=plan_id)
            except (User.DoesNotExist, Plan.DoesNotExist) as e:
                logger.error(f"Utilisateur ou plan non trouvé: {str(e)}")
                return
            
            # Créer ou mettre à jour l'abonnement
            subscription, created = Subscription.objects.get_or_create(
                user=user,
                defaults={
                    'plan': plan,
                    'status': 'active',
                    'billing_cycle': billing_cycle,
                    'start_date': timezone.now(),
                    'current_period_end': timezone.now() + timedelta(days=30 if billing_cycle == 'monthly' else 365),
                    'stripe_customer_id': customer_id
                }
            )
            
            if not created:
                # Mettre à jour l'abonnement existant
                subscription.plan = plan
                subscription.status = 'active'
                subscription.billing_cycle = billing_cycle
                subscription.start_date = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30 if billing_cycle == 'monthly' else 365)
                subscription.stripe_customer_id = customer_id
                subscription.save()
            
            # Créer l'entrée dans l'historique des paiements
            amount = session.get('amount_total', 0) / 100  # Conversion des centimes en FCFA
            PaymentHistory.objects.create(
                subscription=subscription,
                amount=amount,
                payment_date=timezone.now(),
                stripe_invoice_id=session.get('invoice'),
                stripe_payment_intent_id=session.get('payment_intent'),
                status='paid',
                payment_method='card'
            )
            
            logger.info(f"{'Nouvel' if created else 'Mise à jour'} abonnement pour l'utilisateur {user.email}: Plan {plan.name}")
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la session de paiement: {str(e)}")
            raise

    @classmethod
    def get_stripe_customer_id(cls, user):
        """
        Récupère ou crée un ID client Stripe pour l'utilisateur
        
        Args:
            user: L'utilisateur pour lequel récupérer ou créer l'ID client
            
        Returns:
            L'ID client Stripe
        """
        # Vérifier si l'utilisateur a déjà un ID client Stripe
        if hasattr(user, 'stripe_customer_id') and user.stripe_customer_id:
            return user.stripe_customer_id
            
        # Si l'utilisateur a un abonnement avec un ID client
        if hasattr(user, 'subscription') and user.subscription and user.subscription.stripe_customer_id:
            return user.subscription.stripe_customer_id
            
        # Sinon, créer un nouveau client Stripe
        return cls.create_customer(user)
