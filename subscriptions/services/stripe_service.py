from django.conf import settings
import stripe
from django.utils import timezone

class StripeService:
    @classmethod
    def create_customer(cls, user):
        """Crée un client Stripe pour l'utilisateur"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Créer le client
        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}",
            metadata={
                'user_id': user.id
            }
        )
        
        # Mettre à jour l'utilisateur avec l'ID client Stripe
        user.stripe_customer_id = customer.id
        user.save(update_fields=['stripe_customer_id'])
        
        return customer.id
    
    @classmethod
    def create_checkout_session(cls, user, plan, billing_cycle='monthly', subscription=None):
        """Crée une session de paiement Stripe"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Si l'utilisateur n'a pas d'ID client Stripe, en créer un
        if not hasattr(user, 'stripe_customer_id') or not user.stripe_customer_id:
            cls.create_customer(user)
            
        # Déterminer le prix à utiliser en fonction du cycle de facturation
        # Vérifier d'abord si nous avons un ID de prix Stripe
        if billing_cycle == 'monthly':
            stripe_price_id = plan.stripe_price_id_monthly
            amount = plan.price_monthly
        else:
            stripe_price_id = plan.stripe_price_id_annually
            amount = plan.price_annually
        
        # Vérifier que l'ID de prix est valide (doit commencer par 'price_')
        use_price_id = stripe_price_id is not None and isinstance(stripe_price_id, str) and stripe_price_id.startswith('price_')
        
        # Si nous n'avons pas d'ID de prix Stripe valide et que le plan n'est pas gratuit, essayer de le créer
        if not use_price_id and amount > 0:
            try:
                # Créer les produits et prix Stripe pour ce plan
                result = cls.create_stripe_product_and_prices(plan)
                
                # Récupérer l'ID de prix nouvellement créé
                if billing_cycle == 'monthly':
                    stripe_price_id = result.get('price_id_monthly')
                else:
                    stripe_price_id = result.get('price_id_annually')
                    
                use_price_id = stripe_price_id is not None and isinstance(stripe_price_id, str) and stripe_price_id.startswith('price_')
            except Exception as e:
                print(f"Erreur lors de la création des prix Stripe: {str(e)}")
        
        # Si on n'a toujours pas d'ID de prix valide, lever une erreur
        if not use_price_id and amount > 0:
            raise ValueError(f"Aucun ID de prix Stripe valide trouvé pour le plan {plan.name} ({plan.id}) avec cycle {billing_cycle}. "
                          f"ID actuel: {stripe_price_id}")
        
        # Paramètres Stripe de base
        session_params = {
            'customer': user.stripe_customer_id,
            'payment_method_types': ['card'],
            'mode': 'subscription',
            'success_url': settings.STRIPE_SUCCESS_URLs,
            'cancel_url': settings.STRIPE_CANCEL_URL,
            'metadata': {
                'user_id': user.id,
                'plan_id': plan.id,
                'billing_cycle': billing_cycle
            },
            'allow_promotion_codes': True
        }
        
        # Définition des éléments de ligne en fonction de la disponibilité d'un ID de prix
        if use_price_id:
            # Utiliser l'ID de prix Stripe
            session_params['line_items'] = [{
                'price': stripe_price_id,
                'quantity': 1
            }]
        else:
            # Plan gratuit ou autre cas spécial
            if amount <= 0:
                # Pour les plans gratuits, créer un abonnement sans paiement
                return {'url': settings.STRIPE_SUCCESS_URLs}
            else:
                # Ne devrait pas arriver car on lève une exception plus haut
                raise ValueError("Impossible de créer une session de paiement sans ID de prix Stripe")
            
        # Créer la session de paiement
        checkout_session = stripe.checkout.Session.create(**session_params)
        
        return checkout_session
    
    @classmethod
    def create_stripe_product_and_prices(cls, plan):
        """Crée un produit Stripe et ses prix pour un plan donné"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Créer le produit s'il n'existe pas déjà
        if not plan.stripe_product_id:
            product = stripe.Product.create(
                name=plan.name,
                description=plan.description,
                metadata={
                    'plan_id': plan.id,
                    'plan_type': plan.plan_type
                }
            )
            plan.stripe_product_id = product.id
        
        # Créer les prix pour le produit
        # Prix mensuel
        if not plan.stripe_price_id_monthly and plan.price_monthly > 0:
            price_monthly = stripe.Price.create(
                product=plan.stripe_product_id,
                unit_amount=int(plan.price_monthly ),  # Stripe utilise les centimes
                currency='xof',
                recurring={
                    'interval': 'month',
                    'interval_count': 1
                },
                metadata={
                    'plan_id': plan.id,
                    'billing_cycle': 'monthly'
                }
            )
            plan.stripe_price_id_monthly = price_monthly.id
        
        # Prix annuel
        if not plan.stripe_price_id_annually and plan.price_annually > 0:
            price_annually = stripe.Price.create(
                product=plan.stripe_product_id,
                unit_amount=int(plan.price_annually ),  # Stripe utilise les centimes
                currency='xof',
                recurring={
                    'interval': 'year',
                    'interval_count': 1
                },
                metadata={
                    'plan_id': plan.id,
                    'billing_cycle': 'annually'
                }
            )
            plan.stripe_price_id_annually = price_annually.id
        
        # Sauvegarder les modifications
        plan.save(update_fields=['stripe_product_id', 'stripe_price_id_monthly', 'stripe_price_id_annually'])
        
        return {
            'product_id': plan.stripe_product_id,
            'price_id_monthly': plan.stripe_price_id_monthly,
            'price_id_annually': plan.stripe_price_id_annually
        }
    
    @classmethod
    def update_stripe_prices(cls, plan):
        """Met à jour les prix Stripe pour un plan existant"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Créer le produit s'il n'existe pas
        if not plan.stripe_product_id:
            return cls.create_stripe_product_and_prices(plan)
        
        # Mise à jour des prix: Stripe ne permet pas de modifier un prix existant
        # Nous devons donc en créer de nouveaux et les associer au plan
        
        # Prix mensuel
        if plan.price_monthly > 0:
            price_monthly = stripe.Price.create(
                product=plan.stripe_product_id,
                unit_amount=int(plan.price_monthly ),
                currency='xof',
                recurring={
                    'interval': 'month',
                    'interval_count': 1
                },
                metadata={
                    'plan_id': plan.id,
                    'billing_cycle': 'monthly'
                }
            )
            plan.stripe_price_id_monthly = price_monthly.id
        
        # Prix annuel
        if plan.price_annually > 0:
            price_annually = stripe.Price.create(
                product=plan.stripe_product_id,
                unit_amount=int(plan.price_annually ),
                currency='xof',
                recurring={
                    'interval': 'year',
                    'interval_count': 1
                },
                metadata={
                    'plan_id': plan.id,
                    'billing_cycle': 'annually'
                }
            )
            plan.stripe_price_id_annually = price_annually.id
        
        # Sauvegarder les modifications
        plan.save(update_fields=['stripe_price_id_monthly', 'stripe_price_id_annually'])
        
        return {
            'price_id_monthly': plan.stripe_price_id_monthly,
            'price_id_annually': plan.stripe_price_id_annually
        }
    
    @classmethod
    def cancel_subscription(cls, subscription):
        """Annule un abonnement Stripe"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        if not subscription.stripe_subscription_id:
            return {'status': 'success', 'message': 'Aucun abonnement Stripe à annuler'}
        
        # Annuler l'abonnement Stripe
        try:
            stripe_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Mettre à jour l'abonnement local
            subscription.canceled_at = timezone.now()
            subscription.status = 'canceled'
            subscription.save(update_fields=['canceled_at', 'status'])
            
            return {
                'status': 'success',
                'message': 'Abonnement annulé avec succès',
                'stripe_subscription': stripe_subscription
            }
        except stripe.error.StripeError as e:
            return {'status': 'error', 'message': str(e)}
    
    @classmethod
    def process_webhook_event(cls, payload, sig_header):
        """Traite les événements webhook de Stripe"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError as e:
            return {'error': 'Payload invalide'}
        except stripe.error.SignatureVerificationError as e:
            return {'error': 'Signature invalide'}
            
        # Traiter les différents types d'événements
        event_type = event['type']
        event_data = event['data']['object']
        
        print(f"Événement Stripe reçu: {event_type}")
        
        # Implémentez ici le traitement des événements spécifiques
        if event_type == 'checkout.session.completed':
            cls._handle_checkout_session_completed(event)
        elif event_type == 'invoice.paid':
            cls._handle_invoice_paid(event)
        elif event_type == 'customer.subscription.updated':
            cls._handle_subscription_updated(event)
        elif event_type == 'customer.subscription.deleted':
            cls._handle_subscription_deleted(event)
        
        return {'status': 'success', 'event_type': event_type}
        
    @classmethod
    def _handle_checkout_session_completed(cls, event):
        """Gère l'événement de complétion d'une session de paiement"""
        from ..models import Subscription, Plan
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        from datetime import timedelta
        
        User = get_user_model()
        session = event['data']['object']
        
        print(f"Traitement de la session complétée: {session.id}")
        
        # Récupérer les informations de la session
        user_id = session.get('metadata', {}).get('user_id')
        plan_id = session.get('metadata', {}).get('plan_id')
        billing_cycle = session.get('metadata', {}).get('billing_cycle', 'monthly')
        
        if not user_id or not plan_id:
            print(f"Métadonnées manquantes: user_id={user_id}, plan_id={plan_id}")
            return
            
        try:
            user = User.objects.get(id=user_id)
            plan = Plan.objects.get(id=plan_id)
            
            # Vérifier si l'utilisateur a déjà un abonnement
            try:
                subscription = Subscription.objects.get(user=user)
                
                # Mettre à jour l'abonnement existant
                subscription.plan = plan
                subscription.status = 'active'
                subscription.billing_cycle = billing_cycle
                
                # Si l'ID client n'est pas défini, l'ajouter
                if not subscription.stripe_customer_id and session.get('customer'):
                    subscription.stripe_customer_id = session.get('customer')
                    
                # Si l'ID d'abonnement n'est pas défini, essayer de le récupérer
                if not subscription.stripe_subscription_id and session.get('subscription'):
                    subscription.stripe_subscription_id = session.get('subscription')
                
                # Mettre à jour les dates
                subscription.start_date = timezone.now()
                if billing_cycle == 'monthly':
                    subscription.current_period_end = timezone.now() + timedelta(days=30)
                else:
                    subscription.current_period_end = timezone.now() + timedelta(days=365)
                
                subscription.save()
                print(f"Abonnement mis à jour pour l'utilisateur {user.email}")
                
            except Subscription.DoesNotExist:
                # Créer un nouvel abonnement
                subscription = Subscription.objects.create(
                    user=user,
                    plan=plan,
                    status='active',
                    billing_cycle=billing_cycle,
                    start_date=timezone.now(),
                    current_period_end=timezone.now() + timedelta(days=30 if billing_cycle == 'monthly' else 365),
                    stripe_customer_id=session.get('customer'),
                    stripe_subscription_id=session.get('subscription')
                )
                print(f"Nouvel abonnement créé pour l'utilisateur {user.email}")
                
        except User.DoesNotExist:
            print(f"Utilisateur non trouvé: {user_id}")
        except Plan.DoesNotExist:
            print(f"Plan non trouvé: {plan_id}")
        except Exception as e:
            print(f"Erreur lors du traitement de la session: {str(e)}")
            
    @classmethod
    def _handle_invoice_paid(cls, event):
        """Gère un paiement d'invoice réussi"""
        # Implémentation à ajouter si nécessaire
        pass
        
    @classmethod
    def _handle_subscription_updated(cls, event):
        """Gère la mise à jour d'un abonnement"""
        # Implémentation à ajouter si nécessaire
        pass
        
    @classmethod
    def _handle_subscription_deleted(cls, event):
        """Gère la suppression d'un abonnement"""
        # Implémentation à ajouter si nécessaire
        pass
    
    @classmethod
    def sync_all_plans(cls):
        """Synchronise tous les plans actifs avec Stripe"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        from ..models import Plan
        
        # Récupérer tous les plans actifs non gratuits
        plans = Plan.objects.filter(
            is_active=True,
            plan_type__in=['professionnel', 'entreprise', 'gouvernement']
        )
        
        results = {
            'success': [],
            'errors': []
        }
        
        for plan in plans:
            try:
                # Vérifier si le plan a déjà un produit Stripe
                if not plan.stripe_product_id:
                    # Créer un nouveau produit
                    product = stripe.Product.create(
                        name=plan.name,
                        description=plan.description if plan.description else plan.name,
                        metadata={
                            'plan_id': str(plan.id),
                            'plan_type': plan.plan_type
                        }
                    )
                    plan.stripe_product_id = product.id
                
                # Créer ou mettre à jour les prix
                # Prix mensuel
                if not plan.stripe_price_id_monthly and plan.price_monthly > 0:
                    price_monthly = stripe.Price.create(
                        product=plan.stripe_product_id,
                        unit_amount=int(float(plan.price_monthly)),  # Stripe utilise les centimes
                        currency='xof',
                        recurring={
                            'interval': 'month',
                            'interval_count': 1
                        },
                        metadata={
                            'plan_id': str(plan.id),
                            'billing_cycle': 'monthly'
                        }
                    )
                    plan.stripe_price_id_monthly = price_monthly.id
                
                # Prix annuel
                if not plan.stripe_price_id_annually and plan.price_annually > 0:
                    price_annually = stripe.Price.create(
                        product=plan.stripe_product_id,
                        unit_amount=int(float(plan.price_annually)),  # Stripe utilise les centimes
                        currency='xof',
                        recurring={
                            'interval': 'year',
                            'interval_count': 1
                        },
                        metadata={
                            'plan_id': str(plan.id),
                            'billing_cycle': 'annually'
                        }
                    )
                    plan.stripe_price_id_annually = price_annually.id
                
                # Sauvegarder les modifications
                plan.save(update_fields=['stripe_product_id', 'stripe_price_id_monthly', 'stripe_price_id_annually'])
                
                # Récupérer le plan actualisé
                updated_plan = Plan.objects.get(id=plan.id)
                
                results['success'].append({
                    'plan_id': plan.id,
                    'name': plan.name,
                    'stripe_product_id': updated_plan.stripe_product_id,
                    'stripe_price_id_monthly': updated_plan.stripe_price_id_monthly,
                    'stripe_price_id_annually': updated_plan.stripe_price_id_annually
                })
                
            except Exception as e:
                results['errors'].append({
                    'plan_id': plan.id,
                    'name': plan.name,
                    'error': str(e)
                })
        
        return results
    
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