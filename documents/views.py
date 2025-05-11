from itertools import count
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied
from .models import Document, Signature, SavedSignature, DocumentSigner

from .serializers import DocumentSerializer, SignatureSerializer, SignatureDessinSerializer, SavedSignatureSerializer, SavedSignatureListSerializer, DocumentSignerSerializer, DocumentSignerCreateSerializer, DocumentWithSignersSerializer
from .utils import calculate_document_hash, verify_signature,send_notification_email, sign_document
from certificates.models import Certificate
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
import os
from .pdf_signer import sign_pdf_with_base64, PDFSignatureManager
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.mail import send_mail

import logging

logger = logging.getLogger(__name__)

class SavedSignatureViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les signatures sauvegardées des utilisateurs.
    """
    serializer_class = SavedSignatureSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Retourne uniquement les signatures de l'utilisateur connecté"""
        return SavedSignature.objects.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """Utilise un sérialiseur différent pour la liste (sans les données sensibles)"""
        if self.action == 'list':
            return SavedSignatureListSerializer
        return SavedSignatureSerializer
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Définit une signature comme signature par défaut"""
        signature = self.get_object()
        signature.is_default = True
        signature.save()  # Le modèle s'occupe de désactiver les autres signatures par défaut
        return Response({'status': 'success'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def get_data(self, request, pk=None):
        """
        Récupère les données déchiffrées de la signature.
        Cette action est sécurisée car elle nécessite une authentification
        et ne renvoie que les signatures de l'utilisateur connecté.
        """
        signature = self.get_object()
        try:
            decrypted_data = signature.decrypt_signature()
            # Marquer la signature comme utilisée
            signature.mark_as_used()
            return Response({'signature_data': decrypted_data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement de la signature: {str(e)}")
            return Response(
                {'error': 'Impossible de récupérer les données de signature'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(uploaded_by=self.request.user)

    def perform_create(self, serializer):
        try:
            with transaction.atomic():  # Début de la transaction
                document = serializer.save(uploaded_by=self.request.user)
                document.hash = calculate_document_hash(document.file)

                # Vérifier si un document avec ce hash existe déjà
                existing_document = Document.objects.filter(hash=document.hash).first()
                if existing_document:
                    logger.error(f"Un document avec le hash {document.hash} existe déjà.")
                    return Response({'error': 'Un document avec ce hash existe déjà'}, status=status.HTTP_400_BAD_REQUEST)

                # Si pas de document existant, enregistrez le nouveau document
                document.save()
                logger.info(f"Document créé : {document.id} par l'utilisateur : {self.request.user.email}")
            return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Erreur lors de la création du document : {str(e)}")
            return Response({'error': 'Une erreur est survenue'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def sign(self, request, pk=None):
        """
        Associe un certificat à un document pour l'authentifier
        
        Paramètres:
        - certificate: ID du certificat à utiliser
        """
        document = self.get_object()
        certificate_id = request.data.get('certificate')
        
        if not certificate_id:
            return Response(
                {"error": "ID du certificat manquant"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Vérifier que le certificat existe et appartient à l'utilisateur
            certificate = get_object_or_404(Certificate, id=certificate_id, user=request.user)
            
            # Mettre à jour le statut du document
            document.status = 'signed'
            document.save()
            
            # Envoyer une notification par email (si configuré)
            try:
                send_notification_email(
                    request.user.email,
                    "Document authentifié",
                    f"Votre document '{document.title}' a été authentifié avec succès."
                )
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi de l'email de notification: {str(e)}")
            
            return Response(
                {"message": "Document authentifié avec succès", "document": DocumentSerializer(document).data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification du document: {str(e)}")
            return Response(
                {"error": f"Erreur lors de l'authentification du document: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def sign_drawn(self, request, pk=None):
        try:
            logger.debug(f"Début de la signature dessinée pour l'utilisateur {request.user.email}")
            with transaction.atomic():
                document = self.get_object()
                serializer = SignatureDessinSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                signature = Signature.objects.create(
                    document=document,
                    signer=request.user,
                    certificate=certificate,
                    drawn_signature=serializer.validated_data['signature'],
                    signature_position_x=serializer.validated_data['position']['x'],
                    signature_position_y=serializer.validated_data['position']['y'],
                    signature_page=serializer.validated_data['position']['page']
                )
                return Response(SignatureSerializer(signature).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Erreur pendant la signature dessinée : {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def download_document(self, request, pk=None):
        document = self.get_object()
        file_path = document.file.path
        
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{document.title}.pdf"'
            return response

    @action(detail=True, methods=['post'])
    def sign_pdf(self, request, pk=None):
        """
        Signe un document PDF avec une signature dessinée
        
        Paramètres:
        - signature: données de signature en base64
        - page: numéro de page (0-indexed)
        - x: position X de la signature
        - y: position Y de la signature
        - width: largeur de la signature
        - height: hauteur de la signature
        - certificate: ID du certificat à associer au document
        """
        document = self.get_object()
        
        subscription = request.user.subscriptions.filter(status='active').order_by('-created_at').first()
        if not subscription :
            return Response(
                    {"error": "Vous n'avez pas d'abonnement actif"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        if subscription.signatures_used >= subscription.custom_max_signatures:
            return Response(
                    {"error": "Vous avez atteint votre limite de signatures pour ce mois"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Vérifier le quota de signatures
        subscription_qs = request.user.subscriptions.filter(status='active').order_by('-created_at')

        if subscription_qs.exists():
            subscription = subscription_qs.first()

            # Vérifier si le plan est de type "découverte"
            if subscription.plan.plan_type != 'decouverte':
                today = timezone.now()
                subscription_end = subscription.current_period_end

                # Vérifie si l'abonnement a expiré
                if subscription_end <= today:
                    return Response(
                        {"error": "Votre abonnement a expiré."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Vérifie si la limite de signatures est atteinte
                if subscription.signatures_used >= subscription.custom_max_signatures:
                    return Response(
                        {"error": "Vous avez atteint votre limite de signatures pour ce mois."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Mettre à jour le quota de signatures
                subscription.signatures_used += 1
                subscription.save()

            else:
                subscription = request.user.subscriptions.first()
                today = timezone.now()  # Cela retourne déjà un datetime avec timezone UTC
                subscription_end = subscription.current_period_end # Retirer le fuseau horaire  

                if subscription_end <= today :
                    return Response(
                            {"error": "Vous avez atteint votre date d'abonnement est expire"},
                            status=status.HTTP_400_BAD_REQUEST
                        
                        )
                if  subscription.signatures_used >= subscription.custom_max_signatures:
                    return Response(
                        {"error": "Vous avez atteint votre limite de signatures pour ce mois"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    # mettre à jour le quota de signatures
                    # signatures_used
                subscription.signatures_used += 1
                subscription.save()  

        # Vérifier que le document est un PDF
        if not document.file.name.lower().endswith('.pdf'):
            return Response(
                {"error": "Le document doit être un fichier PDF"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer les données de signature
        signature_data = request.data.get('signature')
        if not signature_data:
            return Response(
                {"error": "Données de signature manquantes"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer l'ID du certificat status active
        certificate = Certificate.objects.filter(user=request.user, status='active').first()
        if not certificate:
            return Response(
                {"error": "Aucun certificat actif trouvé"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        certificate_id = request.data.get('certificate' )
        if not certificate_id:
            return Response(
                {"error": "ID du certificat manquant"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier que le certificat existe et appartient à l'utilisateur
        try:
            certificate = get_object_or_404(Certificate, id=certificate_id, user=request.user)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du certificat: {str(e)}")
            return Response(
                {"error": f"Certificat introuvable ou non autorisé: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer les coordonnées de la signature
        try:
            page = int(request.data.get('page', 0))
            x = int(request.data.get('x', 100))
            y = int(request.data.get('y', 100))
            width = int(request.data.get('width', 200))
            height = int(request.data.get('height', 100))
            
            # Journaliser les coordonnées reçues
            logger.info(f"Coordonnées reçues du frontend: page={page}, x={x}, y={y}, width={width}, height={height}")
            
            # Vérifier que les coordonnées sont valides
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                return Response(
                    {"error": "Coordonnées de signature invalides (valeurs négatives ou nulles)"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError) as e:
            logger.warning(f"Erreur de conversion des coordonnées: {str(e)}")
            return Response(
                {"error": "Coordonnées de signature invalides"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Chemin du fichier PDF
            pdf_path = document.file.path
            
            # Signer le PDF
            signed_pdf_path = PDFSignatureManager.sign_pdf_with_base64(
                pdf_path, signature_data, page=page, x=x, y=y, width=width, height=height
            )
            
            # Mettre à jour le document avec le fichier signé
            with open(signed_pdf_path, 'rb') as f:
                document.file.save(f"signed_{os.path.basename(document.file.name)}", f, save=True)
            
            
           
                # Mettre à jour le statut du document
            document.status = 'signed'
            document.save()
            
            # Créer une signature avec le certificat et les coordonnées
            signature = Signature.objects.create(
                document=document,
                signer=request.user,
                certificate=certificate,
                signature_data="Signature électronique",
                drawn_signature=signature_data,
                signature_position_x=x,
                signature_position_y=y,
                signature_page=page
            )
            logger.info(f"Certificat {certificate_id} associé au document {document.id}")
            
            


            return Response(
                {"message": "Document signé avec succès", "document": DocumentSerializer(document).data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Erreur lors de la signature du document: {str(e)}")
            return Response(
                {"error": f"Erreur lors de la signature du document: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def verify_signature(self, request, pk=None):
        """
        Vérifie la signature d'un document PDF
        
        Paramètres:
        - signature_id: ID de la signature à vérifier
        
        Retourne:
        - valid: True si la signature est valide, False sinon
        - message: Message explicatif
        - certificate: Informations sur le certificat utilisé pour la signature
        """
        document = self.get_object()
        signature_id = request.data.get('signature_id')
        
        if not signature_id:
            return Response(
                {"error": "ID de signature manquant"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Récupérer la signature
            signature = get_object_or_404(Signature, id=signature_id, document=document)
            
            # Récupérer le certificat associé à la signature
            certificate = signature.certificate
            
            if not certificate:
                return Response(
                    {"valid": False, "message": "Aucun certificat associé à cette signature"},
                    status=status.HTTP_200_OK
                )
            
            # Vérifier que le certificat est valide
            if certificate.status != 'active':
                return Response(
                    {
                        "valid": False, 
                        "message": f"Le certificat utilisé n'est pas actif (statut: {certificate.status})",
                        "certificate": {
                            "id": certificate.id,
                            "name": getattr(certificate, 'name', ''),
                            "status": certificate.status,
                            "valid_from": certificate.valid_from,
                            "valid_until": certificate.valid_until,
                            "user": certificate.user.username
                        }
                    },
                    status=status.HTTP_200_OK
                )
            
            # Vérifier que le certificat n'est pas expiré
            now = timezone.now()
            if certificate.valid_until and certificate.valid_until < now:
                return Response(
                    {
                        "valid": False, 
                        "message": f"Le certificat a expiré le {certificate.valid_until}",
                        "certificate": {
                            "id": certificate.id,
                            "name": getattr(certificate, 'name', ''),
                            "status": certificate.status,
                            "valid_from": certificate.valid_from,
                            "valid_until": certificate.valid_until,
                            "user": certificate.user.username
                        }
                    },
                    status=status.HTTP_200_OK
                )
            
            # Vérifier la signature cryptographique si elle existe
            if signature.signature_data and signature.signature_data != "Signature électronique":
                try:
                    # Calculer le hash du document
                    document_hash = calculate_document_hash(document.file)
                    
                    # Vérifier la signature avec la clé publique du certificat
                    is_valid = verify_signature(
                        signature.signature_data,
                        document_hash,
                        certificate.public_key
                    )
                    
                    if not is_valid:
                        return Response(
                            {
                                "valid": False, 
                                "message": "La signature cryptographique n'est pas valide",
                                "certificate": {
                                    "id": certificate.id,
                                    "name": getattr(certificate, 'name', ''),
                                    "status": certificate.status,
                                    "valid_from": certificate.valid_from,
                                    "valid_until": certificate.valid_until,
                                    "user": certificate.user.username
                                }
                            },
                            status=status.HTTP_200_OK
                        )
                except Exception as e:
                    logger.error(f"Erreur lors de la vérification cryptographique: {str(e)}")
                    return Response(
                        {
                            "valid": False, 
                            "message": f"Erreur lors de la vérification cryptographique: {str(e)}",
                            "certificate": {
                                "id": certificate.id,
                                "name": getattr(certificate, 'name', ''),
                                "status": certificate.status,
                                "valid_from": certificate.valid_from,
                                "valid_until": certificate.valid_until,
                                "user": certificate.user.username
                            }
                        },
                        status=status.HTTP_200_OK
                    )
            
            # Si tout est valide, retourner un succès
            return Response(
                {
                    "valid": True, 
                    "message": "La signature est valide et authentique",
                    "certificate": {
                        "id": certificate.id,
                        "name": getattr(certificate, 'name', ''),
                        "status": certificate.status,
                        "valid_from": certificate.valid_from,
                        "valid_until": certificate.valid_until,
                        "user": certificate.user.username
                    },
                    "signature": {
                        "id": signature.id,
                        "timestamp": signature.timestamp,
                        "signer": signature.signer.username,
                        "has_drawn_signature": bool(signature.drawn_signature)
                    }
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la signature: {str(e)}")
            return Response(
                {"error": f"Erreur lors de la vérification de la signature: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        
    # Admin stats
    @action(detail=False, methods=['get'])
    def stats_admin(self, request):
        # user authentifié
        user = request.user
        
        # user is admin
        # if not user.is_superuser:
        #     return Response(
        #         {"error": "Vous n'êtes pas autorisé à accéder à ces statistiques"},
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        if not user.is_staff:
            return Response(
                {"error": "Vous n'êtes pas autorisé à accéder à ces statistiques"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        
        """
        Retourne les statistiques de documents
        """
        from django.db.models import Count
        from django.db.models import Q
        
        # Récupérer les statistiques de documents
        total_documents = Document.objects.count()
        total_signatures = Signature.objects.count()
        total_certificates = Certificate.objects.count()
        total_pending = Document.objects.filter(status='pending').count()
        
        # Statistiques mensuelles (6 derniers mois)
        from datetime import datetime, timedelta
        import calendar
        
        # Obtenir la date et date actuel
        today = datetime.now()
        six_months_ago = today - timedelta(days=365)
        
        # Statistiques mensuelles des documents
        monthly_stats = []
        for i in range(13):
            month_date = six_months_ago + timedelta(days=30 * i)
            month_name = calendar.month_name[month_date.month][:3]
            
            # Documents créés ce mois
            month_docs = Document.objects.filter(
                created_at__year=month_date.year,
                created_at__month=month_date.month
            ).count()
            
            monthly_stats.append({
                'month': month_name,
                'count': month_docs
            })
        
        stats = {
            'total_documents': total_documents,
            'total_signatures': total_signatures,
            'total_certificates': total_certificates,
            'total_pending': total_pending,
            'monthly_stats': monthly_stats
        }
        
        return Response(stats, status=status.HTTP_200_OK)
    

    # user stats
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Retourne les statistiques de documents pour l'utilisateur authentifié
        """
        from django.db.models import Count
        from django.db.models import Q
        # user authentifié
        user = request.user
     
        
        
        
        # Récupérer les statistiques de documents pour l'utilisateur
        total_documents = Document.objects.filter(uploaded_by=user).count()
        total_signatures = Signature.objects.filter(signer=user).count()
        total_certificates = Certificate.objects.filter(user=user).count()
        total_pending = Document.objects.filter(status='pending', uploaded_by=user).count()
          # Statistiques mensuelles (6 derniers mois)
        from datetime import datetime, timedelta
        import calendar
        
        # Obtenir la date et date actuel
        
        today = datetime.now()
        
        six_months_ago = today - timedelta(days=365)
        
        # Statistiques mensuelles des documents
        monthly_stats = []
        for i in range(13):
            month_date = six_months_ago + timedelta(days=30 * i)
            month_name = calendar.month_name[month_date.month][:3]
            
            # Documents créés ce mois
            month_docs = Document.objects.filter(
                uploaded_by=user,
                created_at__year=month_date.year,
                created_at__month=month_date.month
            ).count()
            
            monthly_stats.append({
                'month': month_name,
                'count': month_docs
            })
        stats = {
            'total_documents': total_documents,
            'total_signatures': total_signatures,
            'total_certificates': total_certificates,
            'total_pending': total_pending,
            'monthly_stats': monthly_stats
        }
        
        return Response(stats, status=status.HTTP_200_OK)   

    @action(detail=True, methods=['post'])
    def sign_with_saved_signature(self, request, pk=None):
        """
        Signe un document PDF avec une signature sauvegardée
        
        Paramètres:
        - saved_signature_id: ID de la signature sauvegardée
        - certificate_id: ID du certificat (optionnel)
        - position_x: position X de la signature
        - position_y: position Y de la signature
        - width: largeur de la signature
        - height: hauteur de la signature
        - page: numéro de page
        """
        document = self.get_object()
    
        
        subscription = request.user.subscriptions.filter(status='active').order_by('-created_at').first()
        if not subscription :
            return Response(
                    {"error": "Vous n'avez pas d'abonnement actif"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        if subscription.signatures_used >= subscription.custom_max_signatures:
            return Response(
                    {"error": "Vous avez atteint votre limite de signatures pour ce mois"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Vérifier le quota de signatures
        subscription_qs = request.user.subscriptions.filter(status='active').order_by('-created_at')

        if subscription_qs.exists():
            subscription = subscription_qs.first()

            # Vérifier si le plan est de type "découverte"
            if subscription.plan.plan_type != 'decouverte':
                today = timezone.now()
                subscription_end = subscription.current_period_end

                # Vérifie si l'abonnement a expiré
                if subscription_end <= today:
                    return Response(
                        {"error": "Votre abonnement a expiré."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Vérifie si la limite de signatures est atteinte
                if subscription.signatures_used >= subscription.custom_max_signatures:
                    return Response(
                        {"error": "Vous avez atteint votre limite de signatures pour ce mois."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Mettre à jour le quota de signatures
                subscription.signatures_used += 1
                subscription.save()

            else:
                subscription = request.user.subscriptions.first()
                today = timezone.now()  # Cela retourne déjà un datetime avec timezone UTC
                subscription_end = subscription.current_period_end # Retirer le fuseau horaire  

                if subscription_end <= today :
                    return Response(
                            {"error": "Vous avez atteint votre date d'abonnement est expire"},
                            status=status.HTTP_400_BAD_REQUEST
                        
                        )
                if subscription.signatures_used >= subscription.custom_max_signatures:
                    return Response(
                        {"error": "Vous avez atteint votre limite de signatures pour ce mois"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    # mettre à jour le quota de signatures
                    # signatures_used
                subscription.signatures_used += 1
                subscription.save()  
              
        # Vérifier que le document est un PDF
        if not document.file.name.lower().endswith('.pdf'):
            return Response(
                {"error": "Le document doit être un fichier PDF"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer les paramètres
        saved_signature_id = request.data.get('saved_signature_id')
        certificate_id = request.data.get('certificate_id')
        
        if not saved_signature_id:
            return Response(
                {"error": "ID de signature sauvegardée manquant"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer la signature sauvegardée
        try:
            saved_signature = SavedSignature.objects.get(id=saved_signature_id, user=request.user)
        except SavedSignature.DoesNotExist:
            return Response(
                {"error": "Signature sauvegardée introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Récupérer le certificat si fourni
        certificate = None
        if certificate_id:
            try:
                certificate = Certificate.objects.get(id=certificate_id, user=request.user)
                if certificate.status != 'active':
                    return Response(
                        {"error": f"Le certificat n'est pas actif (statut: {certificate.status})"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Certificate.DoesNotExist:
                return Response(
                    {"error": "Certificat introuvable"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Récupérer les coordonnées
        try:
            position_x = float(request.data.get('position_x', 0))
            position_y = float(request.data.get('position_y', 0))
            width = float(request.data.get('width', 0))
            height = float(request.data.get('height', 0))
            page = int(request.data.get('page', 0))
            
            if position_x < 0 or position_y < 0 or width <= 0 or height <= 0 or page < 0:
                return Response(
                    {"error": "Coordonnées de signature invalides"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError) as e:
            logger.warning(f"Erreur de conversion des coordonnées: {str(e)}")
            return Response(
                {"error": "Coordonnées de signature invalides"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Récupérer les données de signature
            signature_data = saved_signature.decrypt_signature()
            
            # Marquer la signature comme utilisée
            saved_signature.mark_as_used()
            
            # Chemin du fichier PDF
            pdf_path = document.file.path
            
            # Signer le PDF
            signed_pdf_path = PDFSignatureManager.sign_pdf_with_base64(
                pdf_path, signature_data, page=page, x=position_x, y=position_y, width=width, height=height
            )
            
            # Mettre à jour le document avec le fichier signé
            with open(signed_pdf_path, 'rb') as f:
                document.file.save(f"signed_{os.path.basename(document.file.name)}", f, save=True)
            
            
                # Mettre à jour le statut du document
            document.status = 'signed'
            document.save()
            
            # Créer une signature avec le certificat et les coordonnées
            signature = Signature.objects.create(
                document=document,
                signer=request.user,
                certificate=certificate,
                signature_data="Signature électronique",
                drawn_signature=signature_data,
                signature_position_x=position_x,
                signature_position_y=position_y,
                signature_page=page,
                saved_signature=saved_signature
            )
            
            return Response(
                {"message": "Document signé avec succès", "document": DocumentSerializer(document).data},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Erreur lors de la signature du document: {str(e)}")
            return Response(
                {"error": f"Erreur lors de la signature du document: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Utiliser le sérialiseur complet avec les signataires pour le détail
        serializer = DocumentWithSignersSerializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def signerss(self, request, pk=None):
        """Liste tous les signataires d'un document"""
        document = self.get_object()
        
        # Vérifier que l'utilisateur est autorisé à voir les signataires
        if document.uploaded_by != request.user:
            return Response(
                {"error": "Vous n'êtes pas autorisé à voir les signataires de ce document."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        signers = DocumentSigner.objects.filter(document=document)
        serializer = DocumentSignerSerializer(signers, many=True)
        return Response(serializer.data)

class DocumentSignerViewSet(viewsets.ModelViewSet):
    """
    Vues pour gérer les signataires d'un document
    """
    serializer_class = DocumentSignerSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_permissions(self):
        """
        Définit les permissions en fonction de l'action
        """
        if self.action == 'sign_pdf_with_token':
            return []  # Pas de permission requise pour sign_pdf_with_token
        return [IsAuthenticated()]
    
    def get_queryset(self):
        # Filtrer par document si spécifié
        document_id = self.kwargs.get('document_id')
        if document_id:
            return DocumentSigner.objects.filter(document__id=document_id)
        
        # Sinon, retourner tous les signataires des documents où l'utilisateur est le propriétaire
        return DocumentSigner.objects.filter(document__uploaded_by=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentSignerCreateSerializer
        return DocumentSignerSerializer
    
    def create(self, request, *args, **kwargs):
        # Récupérer le document
        document_id = kwargs.get('document_id')
        try:
            document = Document.objects.get(id=document_id, uploaded_by=request.user)
        except Document.DoesNotExist:
            return Response(
                {"error": "Document non trouvé ou vous n'êtes pas autorisé à y ajouter des signataires."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Vérifier le forfait pour le nombre de signataires
        try:
            subscription = request.user.subscriptions.filter(status='active').first()
            if subscription and subscription.plan.max_signers > 0:
                current_signers = DocumentSigner.objects.filter(document=document).count()
                if current_signers >= subscription.plan.max_signers:
                    return Response(
                        {"error": f"Votre forfait permet un maximum de {subscription.plan.max_signers} signataires par document."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du forfait: {str(e)}")
        
        # Créer le signataire
        serializer = self.get_serializer(data=request.data, context={'document': document})
        serializer.is_valid(raise_exception=True)
        
        # Ajouter le document
        signer = serializer.save(document=document)
        
        # Envoyer l'invitation immédiatement
        try:
            # subject = f"Invitation à signer le document : {document.title}"
            # message = f"Bonjour {signer.full_name},\n\nVous avez été invité à signer le document '{document.title}'. Cliquez sur le lien pour signer."
            # send_notification_email(subject, message, [signer.email])

            signer.send_invitation()
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'invitation: {str(e)}")
            return Response(
                {"error": f"Le signataire a été créé mais l'invitation n'a pas pu être envoyée: {str(e)}"},
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def send_reminder(self, request, pk=None, document_id=None):
        """Envoyer un rappel au signataire"""
        signer = self.get_object()
        
        if signer.document.uploaded_by != request.user:
            return Response(
                {"error": "Vous n'êtes pas autorisé à envoyer des rappels pour ce document."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if signer.status != 'pending':
            return Response(
                {"error": "Impossible d'envoyer un rappel pour un signataire qui n'est pas en attente."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            signer.send_reminder()
            return Response({"message": "Rappel envoyé avec succès."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Erreur lors de l'envoi du rappel: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def cancel_invitation(self, request, pk=None, document_id=None):
        """Annuler l'invitation d'un signataire"""
        signer = self.get_object()
        
        if signer.document.uploaded_by != request.user:
            return Response(
                {"error": "Vous n'êtes pas autorisé à annuler cette invitation."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if signer.status == 'signed':
            return Response(
                {"error": "Impossible d'annuler une invitation pour un document déjà signé."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        signer.status = 'expired'
        signer.save(update_fields=['status'])
        
        return Response({"message": "Invitation annulée avec succès."}, status=status.HTTP_200_OK)
    @action(detail=False, methods=['post'], url_path='sign_pdf_with_token')
    def sign_pdf_with_token(self, request, *args, **kwargs):
        """
        Signe un document PDF avec une signature dessinée pour un utilisateur invité
        
        Paramètres:
        - token: token du signataire
        - signature_position_x: position X de la signature
        - signature_position_y: position Y de la signature
        - signature_page: numéro de page
        - message: message optionnel
        - notes: notes optionnelles
        """
        try:
            # Récupérer le document
            document_id = kwargs.get('document_id')
            if not document_id:
                return Response(
                    {"error": "ID du document manquant"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            document = Document.objects.get(id=document_id)
            
            # Récupérer le token du signataire depuis la requête
            token = request.data.get('token')
            if not token:
                return Response(
                    {"error": "Token du signataire manquant"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Trouver le signataire avec ce token
            signer = DocumentSigner.objects.get(document=document, token=token)
            
            # Vérifier que le signataire est en attente
            # if signer.status != 'pending':
            #     return Response(
            #         {"error": "Le signataire n'est pas en attente de signature"},
            #         status=status.HTTP_400_BAD_REQUEST
            #     )
            
            # Vérifier que l'invitation n'a pas expiré
            if signer.is_expired():
                return Response(
                    {"error": "L'invitation a expiré"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Récupérer les coordonnées de la signature
            try:
                position_x = int(request.data.get('signature_position_x', 0))
                position_y = int(request.data.get('signature_position_y', 0))
                page = int(request.data.get('signature_page', 0))
                
                # Vérifier que les coordonnées sont valides
                if position_x < 0 or position_y < 0 or page < 0:
                    return Response(
                        {"error": "Coordonnées de signature invalides (valeurs négatives)"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError) as e:
                logger.warning(f"Erreur de conversion des coordonnées: {str(e)}")
                return Response(
                    {"error": "Coordonnées de signature invalides"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mettre à jour les informations de signature
            signer.signature_position_x = position_x
            signer.signature_position_y = position_y
            signer.signature_page = page
            signer.notes = request.data.get('notes', '')
            signer.message = request.data.get('message', '')
            
            # Marquer le signataire comme ayant signé
            signer.mark_as_signed()
            
            return Response(
                {"message": "Document signé avec succès", "document": DocumentSerializer(document).data},
                status=status.HTTP_200_OK
            )
            
        except Document.DoesNotExist:
            return Response(
                {"error": "Document non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )
        except DocumentSigner.DoesNotExist:
            return Response(
                {"error": "Token de signature invalide"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur lors de la signature du document: {str(e)}")
            return Response(
                {"error": f"Erreur lors de la signature du document: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    # @action(detail=True, methods=['post'])
    # def sign_pdf_with_tokenss(self, request, pk=None, document_id=None):
    #     """
    #     Signe un document PDF avec une signature dessinée pour un utilisateur invité
        
    #     Paramètres:
    #     - signature: données de signature en base64
    #     - page: numéro de page (0-indexed)
    #     - x: position X de la signature
    #     - y: position Y de la signature
    #     - width: largeur de la signature
    #     - height: hauteur de la signature
    #     - token: token du signataire
    #     """
    #     try:
    #         # Récupérer le document et le signataire
    #         document = Document.objects.get(id=document_id)
    #         signer = DocumentSigner.objects.get(id=pk, document=document)
    #     except (Document.DoesNotExist, DocumentSigner.DoesNotExist):
    #         return Response(
    #             {"error": "Document ou signataire non trouvé"},
    #             status=status.HTTP_404_NOT_FOUND
    #         )
        
    #     # Vérifier que le signataire est en attente
    #     if signer.status != 'pending':
    #         return Response(
    #             {"error": "Le signataire n'est pas en attente de signature"},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )
        
    #     # Vérifier que l'invitation n'a pas expiré
    #     if signer.is_expired():
    #         return Response(
    #             {"error": "L'invitation a expiré"},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )
        
    #     # Récupérer les données de signature
    #     signature_data = request.data.get('signature')
    #     if not signature_data:
    #         return Response(
    #             {"error": "Données de signature manquantes"},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )
        
    #     # Récupérer les coordonnées de la signature
    #     try:
    #         page = int(request.data.get('page', 0))
    #         x = int(request.data.get('x', 100))
    #         y = int(request.data.get('y', 100))
    #         width = int(request.data.get('width', 200))
    #         height = int(request.data.get('height', 100))
            
    #         if x < 0 or y < 0 or width <= 0 or height <= 0:
    #             return Response(
    #                 {"error": "Coordonnées de signature invalides"},
    #                 status=status.HTTP_400_BAD_REQUEST
    #             )
    #     except (ValueError, TypeError) as e:
    #         return Response(
    #             {"error": "Coordonnées de signature invalides"},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )
        
    #     try:
    #         # Chemin du fichier PDF
    #         pdf_path = document.file.path
            
    #         # Signer le PDF
    #         signed_pdf_path = PDFSignatureManager.sign_pdf_with_base64(
    #             pdf_path, signature_data, page=page, x=x, y=y, width=width, height=height
    #         )
            
    #         # Mettre à jour le document avec le fichier signé
    #         with open(signed_pdf_path, 'rb') as f:
    #             document.file.save(f"signed_{os.path.basename(document.file.name)}", f, save=True)
            
    #         # Mettre à jour le statut du document
    #         document.status = 'signed'
    #         document.save()
            
    #         # Créer une signature
    #         signature = Signature.objects.create(
    #             document=document,
    #             signer=signer.user if signer.user else None,
    #             certificate=None,  # Pas de certificat pour les utilisateurs invités
    #             signature_data="Signature électronique",
    #             drawn_signature=signature_data,
    #             signature_position_x=x,
    #             signature_position_y=y,
    #             signature_page=page
    #         )
            
    #         # Marquer le signataire comme ayant signé
    #         signer.mark_as_signed()
            
    #         return Response(
    #             {"message": "Document signé avec succès", "document": DocumentSerializer(document).data},
    #             status=status.HTTP_200_OK
    #         )
    #     except Exception as e:
    #         logger.error(f"Erreur lors de la signature du document: {str(e)}")
    #         return Response(
    #             {"error": f"Erreur lors de la signature du document: {str(e)}"},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )






