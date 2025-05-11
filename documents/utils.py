import hashlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
def calculate_document_hash(file):
    """Calculate SHA-256 hash of uploaded document."""
    sha256_hash = hashlib.sha256()
    try:
        for chunk in file.chunks():
            sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as e:
        raise Exception(f"Error calculating hash: {str(e)}")

def verify_signature(signature, document_hash, public_key_pem):
    """
    Vérifie une signature numérique à l'aide d'une clé publique.
    
    Args:
        signature (str): Signature en base64
        document_hash (str): Hash SHA-256 du document
        public_key_pem (str): Clé publique au format PEM
        
    Returns:
        bool: True si la signature est valide, False sinon
    """
    try:
        # Charger la clé publique
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(), 
            backend=default_backend()
        )
        
        # Décoder la signature
        signature_bytes = base64.b64decode(signature)
        
        # Vérifier la signature
        public_key.verify(
            signature_bytes,
            document_hash.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), 
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Si aucune exception n'est levée, la signature est valide
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de la signature: {str(e)}")
        return False

def sign_document(document_hash, private_key_pem):
    """
    Fonction pour signer un hachage de document avec une clé privée.
    """
    try:
        # Charger la clé privée depuis PEM
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )

        # Signer le document hash
        signature = private_key.sign(
            document_hash.encode(),  # Assurez-vous que le hash est sous forme d'octets
            padding.PKCS1v15(),      # Padding RSA
            hashes.SHA256()          # Algorithme de hachage
        )

        return signature.hex()  # Retourner la signature sous forme hexadécimale

    except Exception as e:
        raise Exception(f"Erreur lors de la signature du document : {str(e)}")
def send_notification_email(subject, message, recipient_list, html_message=None):
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            fail_silently=False,
            html_message=html_message,
        )
        logger.info(f"Email envoyé avec succès à {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email : {str(e)}")
        return False