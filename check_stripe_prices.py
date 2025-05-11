#!/usr/bin/env python
"""
Script pour vérifier les objets de prix Stripe
Exécuter avec: python check_stripe_prices.py
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
    
    print("Vérification des objets de prix Stripe...")
    
    # Obtenir tous les objets de prix de Stripe
    prices = stripe.Price.list(limit=100)
    
    print(f"\nNombre de prix trouvés: {len(prices.data)}")
    
    for price in prices.data:
        print(f"\nPrix ID: {price.id}")
        print(f"Produit ID: {price.product}")
        print(f"Montant: {price.unit_amount / 100} {price.currency}")
        print(f"Type de récurrence: {price.recurring.interval if hasattr(price, 'recurring') and price.recurring else 'Non récurrent'}")
        if hasattr(price, 'metadata') and price.metadata:
            print(f"Métadonnées: {price.metadata}")
    
    # Vérifier les plans dans la base de données
    print("\n\nVérification des plans dans la base de données:")
    plans = Plan.objects.all()
    
    for plan in plans:
        print(f"\nPlan: {plan.name} (ID: {plan.id})")
        print(f"Produit Stripe: {plan.stripe_product_id}")
        print(f"Prix mensuel ID: {plan.stripe_price_id_monthly}")
        print(f"Prix annuel ID: {plan.stripe_price_id_annually}")
    
    return 0  # Success

if __name__ == "__main__":
    sys.exit(main()) 