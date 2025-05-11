#!/usr/bin/env python
"""
Script pour forcer la création de nouveaux prix Stripe et les associer aux plans
Exécuter avec: python fix_stripe_prices.py
"""

import os
import sys
import django

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

# Import après configuration de Django
import stripe
from django.conf import settings
from subscriptions.models import Plan

def main():
    """Fonction principale"""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    
    print("Correction des prix Stripe pour les plans...")
    
    # Obtenir tous les plans
    plans = Plan.objects.all()
    
    for plan in plans:
        try:
            print(f"\nTraitement du plan: {plan.name} (ID: {plan.id})")
            
            # Réinitialiser les ID de prix Stripe
            plan.stripe_price_id_monthly = None
            plan.stripe_price_id_annually = None
            
            # Vérifier si le produit existe
            if not plan.stripe_product_id or not plan.stripe_product_id.startswith('prod_'):
                # Créer un nouveau produit
                print("Création d'un nouveau produit Stripe...")
                product = stripe.Product.create(
                    name=plan.name,
                    description=plan.description if plan.description else plan.name,
                    metadata={
                        'plan_id': str(plan.id),
                        'plan_type': plan.plan_type
                    }
                )
                plan.stripe_product_id = product.id
                print(f"Produit créé: {product.id}")
            
            # Prix mensuel
            if plan.price_monthly > 0:
                print("Création du prix mensuel...")
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
                print(f"Prix mensuel créé: {price_monthly.id}")
            
            # Prix annuel
            if plan.price_annually > 0:
                print("Création du prix annuel...")
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
                print(f"Prix annuel créé: {price_annually.id}")
            
            # Sauvegarder les modifications
            plan.save(update_fields=['stripe_product_id', 'stripe_price_id_monthly', 'stripe_price_id_annually'])
            print(f"Plan mis à jour: {plan.id}")
            print(f"  - Produit Stripe: {plan.stripe_product_id}")
            print(f"  - Prix mensuel ID: {plan.stripe_price_id_monthly}")
            print(f"  - Prix annuel ID: {plan.stripe_price_id_annually}")
            
        except Exception as e:
            print(f"Erreur lors du traitement du plan {plan.id}: {str(e)}")
    
    return 0  # Success

if __name__ == "__main__":
    sys.exit(main()) 