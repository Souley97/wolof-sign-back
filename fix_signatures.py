#!/usr/bin/env python
"""
Script pour corriger les signatures existantes en les chiffrant correctement.
"""

import os
import django
from cryptography.fernet import Fernet

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from documents.models import SavedSignature
from django.contrib.auth import get_user_model

User = get_user_model()

def fix_signatures():
    """Corrige les signatures existantes en les chiffrant correctement."""
    # Vérifier si la clé de chiffrement est configurée
    if not hasattr(settings, 'SIGNATURE_ENCRYPTION_KEY'):
        print("ERREUR: Clé de chiffrement non configurée dans settings.py")
        return
    
    key = settings.SIGNATURE_ENCRYPTION_KEY.strip()
    print(f"Clé configurée: {key}")
    
    # Encoder la clé
    key_bytes = key.encode()
    
    # Créer l'objet Fernet
    try:
        f = Fernet(key_bytes)
        print("Création de l'objet Fernet: OK")
    except Exception as e:
        print(f"ERREUR lors de la création de l'objet Fernet: {str(e)}")
        return
    
    # Récupérer toutes les signatures
    signatures = SavedSignature.objects.all()
    print(f"Nombre de signatures à traiter: {signatures.count()}")
    
    fixed_count = 0
    already_encrypted_count = 0
    error_count = 0
    
    for signature in signatures:
        try:
            # Vérifier si les données sont déjà chiffrées
            if signature.signature_data.startswith('gAAAAA'):
                print(f"Signature {signature.id} ({signature.name}) déjà chiffrée")
                already_encrypted_count += 1
                continue
            
            # Chiffrer les données
            print(f"Chiffrement de la signature {signature.id} ({signature.name})...")
            encrypted_data = f.encrypt(signature.signature_data.encode())
            signature.signature_data = encrypted_data.decode()
            signature.save(update_fields=['signature_data'])
            fixed_count += 1
            print(f"Signature {signature.id} corrigée avec succès")
        except Exception as e:
            print(f"ERREUR lors du chiffrement de la signature {signature.id}: {str(e)}")
            error_count += 1
    
    print("\nRésumé:")
    print(f"- Signatures traitées: {signatures.count()}")
    print(f"- Signatures déjà chiffrées: {already_encrypted_count}")
    print(f"- Signatures corrigées: {fixed_count}")
    print(f"- Erreurs: {error_count}")

if __name__ == '__main__':
    print("Correction des signatures existantes...")
    fix_signatures() 