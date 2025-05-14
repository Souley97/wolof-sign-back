import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from subscriptions.models import Plan

# Afficher tous les plans
plans = Plan.objects.all()
print(f"Nombre total de plans: {plans.count()}")

for plan in plans:
    print(f"ID: {plan.id}, Nom: {plan.name}, Type: {plan.plan_type}, Prix mensuel: {plan.price_monthly}")

# Si aucun plan n'existe, en créer un pour tester
if plans.count() == 0:
    print("Aucun plan trouvé. Création d'un plan de test...")
    
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
    
    print(f"Plan de test créé avec ID: {test_plan.id}") 