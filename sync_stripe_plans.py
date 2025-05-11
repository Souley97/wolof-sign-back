#!/usr/bin/env python
"""
Script pour synchroniser tous les plans avec Stripe
Exécuter avec: python sync_stripe_plans.py
"""

import os
import sys
import django

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

# Import après configuration de Django
from subscriptions.services.stripe_service import StripeService
import json

def main():
    """Fonction principale"""
    print("Démarrage de la synchronisation des plans avec Stripe...")
    
    try:
        # Synchroniser tous les plans
        results = StripeService.sync_all_plans()
        
        # Afficher les résultats
        print("\nSynchronisation terminée!")
        print(f"\n{len(results['success'])} plans synchronisés avec succès:")
        for plan in results['success']:
            print(f"- {plan['name']} (ID: {plan['plan_id']})")
            print(f"  Produit Stripe: {plan['stripe_product_id']}")
            print(f"  Prix mensuel: {plan['stripe_price_id_monthly']}")
            print(f"  Prix annuel: {plan['stripe_price_id_annually']}")
            print()
        
        if results['errors']:
            print(f"\n{len(results['errors'])} erreurs rencontrées:")
            for error in results['errors']:
                print(f"- {error['name']} (ID: {error['plan_id']}): {error['error']}")
        
        return 0  # Success
    except Exception as e:
        print(f"Erreur lors de la synchronisation: {str(e)}")
        return 1  # Error

if __name__ == "__main__":
    sys.exit(main()) 