#!/usr/bin/env python
"""
Script pour compter les signatures enregistrées existantes.
"""

import os
import django

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from documents.models import SavedSignature
from django.contrib.auth import get_user_model

User = get_user_model()

def count_signatures():
    """Compte les signatures enregistrées existantes."""
    count = SavedSignature.objects.count()
    print(f"Nombre de signatures enregistrées: {count}")
    
    if count > 0:
        print("\nListe des signatures:")
        for signature in SavedSignature.objects.all():
            print(f"- {signature.name} (ID: {signature.id}, Utilisateur: {signature.user.username})")

if __name__ == '__main__':
    count_signatures() 