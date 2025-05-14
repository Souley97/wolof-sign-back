import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from subscriptions.models import Plan, Subscription
from subscriptions.services.paydunya_service import PayDunyaService
from django.contrib.auth import get_user_model

# Vérifier les clés PayDunya
print("=== Configuration PayDunya ===")
print(f"MASTER_KEY: {'Configurée' if settings.PAYDUNYA_MASTER_KEY else 'Non configurée'}")
print(f"PRIVATE_KEY: {'Configurée' if settings.PAYDUNYA_PRIVATE_KEY else 'Non configurée'}")
print(f"PUBLIC_KEY: {'Configurée' if settings.PAYDUNYA_PUBLIC_KEY else 'Non configurée'}")
print(f"TOKEN: {'Configuré' if settings.PAYDUNYA_TOKEN else 'Non configuré'}")
print(f"BASE_URL: {settings.PAYDUNYA_BASE_URL}")
print("=============================")

# Vérifier si toutes les clés nécessaires sont configurées
if not all([settings.PAYDUNYA_MASTER_KEY, settings.PAYDUNYA_PRIVATE_KEY, 
           settings.PAYDUNYA_PUBLIC_KEY, settings.PAYDUNYA_TOKEN]):
    print("⚠️ ATTENTION: Les clés PayDunya ne sont pas toutes configurées!")
    print("Veuillez configurer les clés PayDunya dans votre fichier .env ou dans settings.py")
    print("Exemple:")
    print("PAYDUNYA_MASTER_KEY=votre_master_key")
    print("PAYDUNYA_PRIVATE_KEY=votre_private_key")
    print("PAYDUNYA_PUBLIC_KEY=votre_public_key")
    print("PAYDUNYA_TOKEN=votre_token")
    sys.exit(1)

# Récupérer un plan
try:
    plan = Plan.objects.get(id=1)
    print(f"✅ Plan trouvé: {plan.name} (ID: {plan.id})")
except Plan.DoesNotExist:
    print("❌ Aucun plan avec ID=1 n'a été trouvé")
    sys.exit(1)

# Récupérer un utilisateur
User = get_user_model()
try:
    user = User.objects.first()
    if not user:
        print("❌ Aucun utilisateur trouvé")
        sys.exit(1)
    print(f"✅ Utilisateur trouvé: {user.email}")
except Exception as e:
    print(f"❌ Erreur lors de la récupération d'un utilisateur: {str(e)}")
    sys.exit(1)

# Récupérer ou créer un abonnement
try:
    # Afficher tous les abonnements de l'utilisateur
    user_subscriptions = Subscription.objects.filter(user=user)
    print(f"L'utilisateur a {user_subscriptions.count()} abonnement(s):")
    
    for idx, sub in enumerate(user_subscriptions):
        print(f"  {idx+1}. ID: {sub.id}, Plan: {sub.plan.name}, Status: {sub.status}")
    
    # Utiliser le premier abonnement ou en créer un nouveau si aucun n'existe
    if user_subscriptions.exists():
        subscription = user_subscriptions.first()
        print(f"✅ Utilisation de l'abonnement existant ID: {subscription.id}")
        
        # Mise à jour de l'abonnement pour utiliser le plan 1
        subscription.plan = plan
        subscription.save()
        print(f"✅ Abonnement mis à jour pour utiliser le plan: {plan.name}")
    else:
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status='pending',
            billing_cycle='monthly'
        )
        print(f"✅ Nouvel abonnement créé avec ID: {subscription.id}")
    
    print(f"Détails de l'abonnement - ID: {subscription.id}, Status: {subscription.status}, Plan: {subscription.plan.name}")
    
except Exception as e:
    print(f"❌ Erreur lors de la gestion de l'abonnement: {str(e)}")
    sys.exit(1)

# Tester l'appel à PayDunya
print("\n=== Tentative d'appel à PayDunya ===")
try:
    # Création d'une demande de paiement
    payment_response = PayDunyaService.create_payment_request(
        subscription=subscription,
        plan=plan,
        billing_cycle='monthly'
    )
    
    print(f"Réponse PayDunya: {payment_response}")
    
    if payment_response.get('success'):
        print("✅ Appel à PayDunya réussi!")
        print(f"URL de checkout: {payment_response.get('checkout_url')}")
        print(f"Token: {payment_response.get('token')}")
    else:
        print(f"❌ Échec de l'appel à PayDunya: {payment_response.get('error')}")
        
except Exception as e:
    import traceback
    print(f"❌ Exception lors de l'appel à PayDunya: {str(e)}")
    print("\nTraceback complet:")
    print(traceback.format_exc()) 