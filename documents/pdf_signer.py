import os
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import base64
from django.conf import settings
import uuid
import logging

# Configurer le logger
logger = logging.getLogger(__name__)

class PDFSignatureManager:
    """
    Classe pour gérer la signature de documents PDF
    """
    
    @staticmethod
    def create_signature_image(signature_data, output_path=None):
        """
        Convertit les données de signature base64 en image
        
        Args:
            signature_data (str): Données de signature en base64
            output_path (str, optional): Chemin de sortie pour l'image. Si None, un chemin temporaire est généré.
        
        Returns:
            str: Chemin de l'image de signature
        """
        try:
            if output_path is None:
                # Créer un nom de fichier unique
                filename = f"signature_{uuid.uuid4()}.png"
                output_path = os.path.join(settings.MEDIA_ROOT, 'signatures', filename)
                
                # S'assurer que le répertoire existe
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Décoder les données base64
            if "data:image" in signature_data:
                # Supprimer le préfixe data:image/png;base64,
                signature_data = signature_data.split(",")[1]
            
            image_data = base64.b64decode(signature_data)
            
            # Sauvegarder l'image
            with open(output_path, "wb") as f:
                f.write(image_data)
            
            return output_path
        except Exception as e:
            logger.error(f"Erreur lors de la création de l'image de signature: {str(e)}")
            raise

    @staticmethod
    def get_pdf_dimensions(pdf_path, page_num=0):
        """
        Obtient les dimensions d'une page de PDF
        
        Args:
            pdf_path (str): Chemin du document PDF
            page_num (int): Numéro de page (0-indexed)
            
        Returns:
            tuple: (largeur, hauteur) de la page en points
        """
        try:
            pdf = PdfReader(pdf_path)
            if page_num >= len(pdf.pages):
                logger.warning(f"Numéro de page invalide: {page_num}. Utilisation de la première page.")
                page_num = 0
                
            page = pdf.pages[page_num]
            # Obtenir les dimensions de la page
            media_box = page.mediabox
            width = float(media_box.width)
            height = float(media_box.height)
            
            return (width, height)
        except Exception as e:
            logger.error(f"Erreur lors de l'obtention des dimensions du PDF: {str(e)}")
            # Retourner les dimensions par défaut de letter
            return (612, 792)  # 8.5 x 11 pouces en points

    @staticmethod
    def add_signature_to_pdf(pdf_path, signature_path, output_path=None, page=0, x=100, y=100, width=200, height=100):
        """
        Ajoute une signature à un document PDF
        
        Args:
            pdf_path (str): Chemin du document PDF
            signature_path (str): Chemin de l'image de signature
            output_path (str, optional): Chemin de sortie pour le PDF signé. Si None, un chemin est généré.
            page (int, optional): Numéro de page où ajouter la signature (0-indexed). Par défaut 0.
            x (int, optional): Position X de la signature. Par défaut 100.
            y (int, optional): Position Y de la signature. Par défaut 100.
            width (int, optional): Largeur de la signature. Par défaut 200.
            height (int, optional): Hauteur de la signature. Par défaut 100.
        
        Returns:
            str: Chemin du PDF signé
        """
        try:
            if output_path is None:
                # Créer un nom de fichier unique
                filename = f"signed_{os.path.basename(pdf_path)}"
                output_path = os.path.join(settings.MEDIA_ROOT, 'signed_documents', filename)
                
                # S'assurer que le répertoire existe
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Obtenir les dimensions du PDF
            pdf_width, pdf_height = PDFSignatureManager.get_pdf_dimensions(pdf_path, page)
            
            # Créer un PDF temporaire avec la signature
            packet = BytesIO()
            c = canvas.Canvas(packet, pagesize=(pdf_width, pdf_height))
            
            # Ajuster les coordonnées Y (dans PDF, l'origine est en bas à gauche)
            # Alors que dans la plupart des interfaces utilisateur, l'origine est en haut à gauche
            adjusted_y = pdf_height - y - height
            
            # Dessiner l'image de signature
            c.drawImage(signature_path, x, adjusted_y, width, height, mask='auto')
            
            # Ajouter des informations de débogage
            logger.debug(f"PDF dimensions: {pdf_width}x{pdf_height}")
            logger.debug(f"Signature position: x={x}, y={y}, adjusted_y={adjusted_y}, width={width}, height={height}")
            
            c.save()
            
            # Déplacer au début du BytesIO
            packet.seek(0)
            
            # Créer un nouveau PDF avec la signature
            new_pdf = PdfReader(packet)
            
            # Lire le PDF existant
            existing_pdf = PdfReader(pdf_path)
            output = PdfWriter()
            
            # Vérifier que le numéro de page est valide
            if page < 0 or page >= len(existing_pdf.pages):
                logger.warning(f"Numéro de page invalide: {page}. Utilisation de la première page.")
                page = 0
            
            # Ajouter la signature à la page spécifiée
            for i, page_obj in enumerate(existing_pdf.pages):
                if i == page:
                    page_obj.merge_page(new_pdf.pages[0])
                output.add_page(page_obj)
            
            # Écrire le PDF de sortie
            with open(output_path, "wb") as f:
                output.write(f)
            
            return output_path
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de la signature au PDF: {str(e)}")
            raise

    @staticmethod
    def sign_pdf_with_base64(pdf_path, signature_data, output_path=None, page=0, x=100, y=100, width=200, height=100):
        """
        Signe un PDF avec une signature en base64
        
        Args:
            pdf_path (str): Chemin du document PDF
            signature_data (str): Données de signature en base64
            output_path (str, optional): Chemin de sortie pour le PDF signé
            page (int, optional): Numéro de page où ajouter la signature
            x (int, optional): Position X de la signature
            y (int, optional): Position Y de la signature
            width (int, optional): Largeur de la signature
            height (int, optional): Hauteur de la signature
        
        Returns:
            str: Chemin du PDF signé
        """
        try:
            # Créer l'image de signature
            signature_path = PDFSignatureManager.create_signature_image(signature_data)
            
            # Journaliser les coordonnées reçues
            logger.info(f"Coordonnées reçues: page={page}, x={x}, y={y}, width={width}, height={height}")
            
            # Ajouter la signature au PDF
            signed_pdf_path = PDFSignatureManager.add_signature_to_pdf(
                pdf_path, signature_path, output_path, page, x, y, width, height
            )
            
            # Supprimer l'image de signature temporaire
            os.remove(signature_path)
            
            return signed_pdf_path
        except Exception as e:
            logger.error(f"Erreur lors de la signature du PDF: {str(e)}")
            raise

# Pour la compatibilité avec le code existant
create_signature_image = PDFSignatureManager.create_signature_image
add_signature_to_pdf = PDFSignatureManager.add_signature_to_pdf
sign_pdf_with_base64 = PDFSignatureManager.sign_pdf_with_base64