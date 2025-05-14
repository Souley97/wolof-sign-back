import os
import django
import logging

# Configuration du logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_paydunya')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from subscriptions.models import Plan, Subscription
from subscriptions.services.paydunya_service import PayDunyaService

# Activer les logs détaillés pour les requêtes
import http.client as http_client
http_client.HTTPConnection.debuglevel = 1

# Récupérer le plan avec ID 1
try:
    plan = Plan.objects.get(id=1)
    logger.info(f"Plan trouvé: ID={plan.id}, Nom={plan.name}, Prix mensuel={plan.price_monthly}")
except Plan.DoesNotExist:
    logger.error("Aucun plan avec ID=1 n'a été trouvé")
    exit(1)

# Tenter de récupérer un utilisateur de test
User = get_user_model()
try:
    user = User.objects.first()  # Utilisez le premier utilisateur comme test
    if not user:
        logger.error("Aucun utilisateur n'est disponible pour le test")
        exit(1)
    logger.info(f"Utilisateur de test: ID={user.id}, Email={user.email}")
except Exception as e:
    logger.error(f"Erreur lors de la récupération d'un utilisateur: {str(e)}")
    exit(1)

# Créer ou récupérer un abonnement pour l'utilisateur
try:
    subscription, created = Subscription.objects.get_or_create(
        user=user,
        defaults={
            'plan': plan,
            'status': 'pending',
            'billing_cycle': 'monthly'
        }
    )
    
    if created:
        logger.info(f"Nouvel abonnement créé pour {user.email}")
    else:
        logger.info(f"Abonnement existant trouvé pour {user.email}")
        # Mise à jour de l'abonnement pour qu'il utilise le plan 1
        subscription.plan = plan
        subscription.save()
    
    logger.info(f"Abonnement: ID={subscription.id}, Status={subscription.status}, Plan={subscription.plan.name}")
    
except Exception as e:
    logger.error(f"Erreur lors de la création/récupération de l'abonnement: {str(e)}")
    exit(1)

# Tester l'appel à PayDunya
try:
    logger.info("Tentative d'appel à PayDunya...")
    
    # Vérifier si les clés PayDunya sont configurées
    from django.conf import settings
    logger.info(f"PAYDUNYA_MASTER_KEY configurée: {'Oui' if settings.PAYDUNYA_MASTER_KEY else 'Non'}")
    logger.info(f"PAYDUNYA_PRIVATE_KEY configurée: {'Oui' if settings.PAYDUNYA_PRIVATE_KEY else 'Non'}")
    logger.info(f"PAYDUNYA_PUBLIC_KEY configurée: {'Oui' if settings.PAYDUNYA_PUBLIC_KEY else 'Non'}")
    logger.info(f"PAYDUNYA_TOKEN configurée: {'Oui' if settings.PAYDUNYA_TOKEN else 'Non'}")
    
    # Tester la création de la demande de paiement
    payment_response = PayDunyaService.create_payment_request(
        subscription=subscription,
        plan=plan,
        billing_cycle='monthly'
    )
    
    logger.info(f"Réponse de PayDunya: {payment_response}")
    
    if payment_response.get('success'):
        logger.info("✅ Appel à PayDunya réussi!")
        logger.info(f"URL de checkout: {payment_response.get('checkout_url')}")
        logger.info(f"Token: {payment_response.get('token')}")
    else:
        logger.error(f"❌ Échec de l'appel à PayDunya: {payment_response.get('error')}")
        
except Exception as e:
    import traceback
    logger.error(f"Exception lors de l'appel à PayDunya: {str(e)}")
    logger.error(traceback.format_exc()) 