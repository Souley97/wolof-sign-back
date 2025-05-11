#!/usr/bin/env python
"""
Script pour tester le déchiffrement d'une signature existante.
"""

import os
import django
import uuid

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from documents.models import SavedSignature

def test_decrypt_signature(signature_id=None):
    """Teste le déchiffrement d'une signature existante."""
    # Si aucun ID n'est fourni, utiliser la première signature trouvée
    if not signature_id:
        signatures = SavedSignature.objects.all()
        if not signatures.exists():
            print("Aucune signature trouvée dans la base de données.")
            return
        signature = signatures.first()
    else:
        try:
            signature_id = uuid.UUID(signature_id)
            signature = SavedSignature.objects.get(id=signature_id)
        except (ValueError, SavedSignature.DoesNotExist):
            print(f"Signature avec l'ID {signature_id} non trouvée.")
            return
    
    print(f"Test de déchiffrement pour la signature {signature.id} ({signature.name})")
    print(f"Données chiffrées: {signature.signature_data[:50]}...")
    
    try:
        # Déchiffrer la signature
        decrypted_data = signature.decrypt_signature()
        print(f"Déchiffrement réussi !")
        print(f"Données déchiffrées (début): {decrypted_data[:50]}...")
        print(f"Longueur des données déchiffrées: {len(decrypted_data)} caractères")
        return decrypted_data
    except Exception as e:
        print(f"ERREUR lors du déchiffrement: {str(e)}")
        return None

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        test_decrypt_signature(sys.argv[1])
    else:
        test_decrypt_signature() 