#!/usr/bin/env python
"""
Script pour supprimer toutes les signatures enregistrées existantes sans demander de confirmation.
À utiliser après avoir changé la clé de chiffrement SIGNATURE_ENCRYPTION_KEY.
"""

import os
import django

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from documents.models import SavedSignature
from django.contrib.auth import get_user_model

User = get_user_model()

def reset_signatures():
    """Supprime toutes les signatures enregistrées existantes."""
    count = SavedSignature.objects.count()
    SavedSignature.objects.all().delete()
    print(f"Toutes les signatures enregistrées ({count}) ont été supprimées.")
    print("Les utilisateurs devront créer de nouvelles signatures.")

if __name__ == '__main__':
    print("Suppression de toutes les signatures enregistrées...")
    reset_signatures() 