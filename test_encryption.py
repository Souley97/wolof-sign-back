#!/usr/bin/env python
"""
Script pour tester le chiffrement et le déchiffrement avec la clé SIGNATURE_ENCRYPTION_KEY.
"""

import os
import django
from cryptography.fernet import Fernet

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

def test_encryption():
    """Teste le chiffrement et le déchiffrement avec la clé configurée."""
    print("Test de chiffrement et déchiffrement")
    print("-" * 50)
    
    # Vérifier si la clé est configurée
    if not hasattr(settings, 'SIGNATURE_ENCRYPTION_KEY'):
        print("ERREUR: Clé de chiffrement non configurée dans settings.py")
        return
    
    key = settings.SIGNATURE_ENCRYPTION_KEY
    print(f"Clé configurée: {key}")
    print(f"Longueur de la clé: {len(key)} caractères")
    
    # Encoder la clé
    key_bytes = key.encode()
    print(f"Clé encodée: {key_bytes}")
    print(f"Longueur de la clé encodée: {len(key_bytes)} bytes")
    
    # Tester le chiffrement et le déchiffrement
    try:
        f = Fernet(key_bytes)
        print("Création de l'objet Fernet: OK")
        
        # Données de test
        test_data = "Ceci est un test de chiffrement et déchiffrement"
        print(f"Données de test: {test_data}")
        
        # Chiffrer
        encrypted_data = f.encrypt(test_data.encode())
        print(f"Données chiffrées: {encrypted_data}")
        
        # Déchiffrer
        decrypted_data = f.decrypt(encrypted_data).decode()
        print(f"Données déchiffrées: {decrypted_data}")
        
        # Vérifier
        if decrypted_data == test_data:
            print("TEST RÉUSSI: Les données déchiffrées correspondent aux données originales")
        else:
            print("TEST ÉCHOUÉ: Les données déchiffrées ne correspondent pas aux données originales")
    
    except Exception as e:
        print(f"ERREUR: {str(e)}")

if __name__ == '__main__':
    test_encryption() 