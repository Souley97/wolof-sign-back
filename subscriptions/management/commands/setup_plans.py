from django.core.management.base import BaseCommand
from subscriptions.models import Plan
from django.conf import settings
import stripe

class Command(BaseCommand):
    help = 'Configure les plans initiaux de Wolof Sign'

    def handle(self, *args, **options):
        # Configurer les plans
        self.setup_plans()
        
        # Configurer les produits et prix Stripe
        if hasattr(settings, 'STRIPE_SECRET_KEY') and settings.STRIPE_SECRET_KEY:
            self.setup_stripe_products()
            
        self.stdout.write(self.style.SUCCESS('Configuration des plans terminée avec succès'))
    
    def setup_plans(self):
        # Plan Découverte (gratuit)
        Plan.objects.update_or_create(
            plan_type='decouverte',
            defaults={
                'name': 'Découverte',
                'description': 'Parfait pour débuter avec la signature électronique',
                'max_signatures': 5,
                'max_signers': 1,
                'storage_limit': 104857600,  # 100 MB en octets
                'retention_days': 30,
                'has_api_access': False,
                'support_level': 'basic',
                'price_monthly': 0,
                'price_annually': 0,
            }
        )
        
        # Plan Professionnel
        Plan.objects.update_or_create(
            plan_type='professionnel',
            defaults={
                'name': 'Professionnel',
                'description': 'Pour les indépendants et petites entreprises',
                'max_signatures': 50,
                'max_signers': 5,
                'storage_limit': 5368709120,  # 5 GB en octets
                'retention_days': 365,
                'has_api_access': False,
                'support_level': 'priority',
                'price_monthly': 15000,
                'price_annually': 144000,  # 12000 * 12 = 144000
            }
        )
        
        # Plan Entreprise
        Plan.objects.update_or_create(
            plan_type='entreprise',
            defaults={
                'name': 'Entreprise',
                'description': 'Pour les PME et organisations en croissance',
                'max_signatures': 0,  # illimité
                'max_signers': 0,  # illimité
                'storage_limit': 21474836480,  # 20 GB en octets
                'retention_days': 1825,  # 5 ans en jours
                'has_api_access': True,
                'support_level': 'dedicated',
                'price_monthly': 45000,
                'price_annually': 432000,  # 36000 * 12 = 432000
            }
        )
        
        # Plan Gouvernement (sur mesure)
        Plan.objects.update_or_create(
            plan_type='gouvernement',
            defaults={
                'name': 'Gouvernement',
                'description': 'Solutions adaptées aux administrations',
                'max_signatures': 0,  # illimité
                'max_signers': 0,  # illimité
                'storage_limit': 107374182400,  # 100 GB en octets
                'retention_days': 3650,  # 10 ans en jours
                'has_api_access': True,
                'support_level': '24/7',
                'price_monthly': 0,  # Tarif sur mesure
                'price_annually': 0,  # Tarif sur mesure
                'is_active': True,
            }
        )
    
    def setup_stripe_products(self):
        """Configure les produits et prix dans Stripe"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        for plan in Plan.objects.filter(is_active=True).exclude(plan_type='decouverte'):
            self.stdout.write(f"Configuration Stripe pour le plan: {plan.name}")
            
            # Créer le produit Stripe
            if not hasattr(plan, 'stripe_product_id') or not plan.stripe_product_id:
                product = stripe.Product.create(
                    name=plan.name,
                    description=plan.description,
                    metadata={'plan_id': plan.id, 'plan_type': plan.plan_type}
                )
                plan.stripe_product_id = product.id
                self.stdout.write(f"  - Produit créé: {product.id}")
            
            # Créer prix mensuel
            if plan.price_monthly > 0 and not plan.stripe_price_id_monthly:
                price = stripe.Price.create(
                    product=plan.stripe_product_id,
                    unit_amount=int(plan.price_monthly ),  # En centimes
                    currency='xof',  # Franc CFA
                    recurring={'interval': 'month'},
                    metadata={'plan_id': plan.id, 'billing_cycle': 'monthly'}
                )
                plan.stripe_price_id_monthly = price.id
                self.stdout.write(f"  - Prix mensuel créé: {price.id}")
            
            # Créer prix annuel
            if plan.price_annually > 0 and not plan.stripe_price_id_annually:
                price = stripe.Price.create(
                    product=plan.stripe_product_id,
                    unit_amount=int(plan.price_annually ),  # En centimes
                    currency='xof',  # Franc CFA
                    recurring={'interval': 'year'},
                    metadata={'plan_id': plan.id, 'billing_cycle': 'annually'}
                )
                plan.stripe_price_id_annually = price.id
                self.stdout.write(f"  - Prix annuel créé: {price.id}")
            
            plan.save()
