import hashlib
from django.db import models
from django.core.exceptions import ValidationError
import os
import uuid
from users.models import User
from certificates.models import Certificate
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth import get_user_model
from cryptography.fernet import Fernet
from subscriptions.models import Subscription
from .utils import send_notification_email
User = get_user_model()


def validate_file_type(file):
    """
    Valide que le fichier est un PDF en vérifiant l'extension et les premiers octets
    """
    # Vérifier l'extension
    ext = os.path.splitext(file.name)[1].lower()
    if ext != '.pdf':
        raise ValidationError('Seuls les fichiers PDF sont autorisés.')
    
    # Vérifier les premiers octets (signature PDF)
    file.seek(0)
    header = file.read(4)
    file.seek(0)  # Réinitialiser le pointeur de fichier
    
    # La signature d'un fichier PDF commence par %PDF (en hexadécimal: 25 50 44 46)
    if header != b'%PDF':
        raise ValidationError('Le fichier ne semble pas être un PDF valide.')


class Signature(models.Model):
    document = models.ForeignKey('Document', on_delete=models.CASCADE)
    signer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE)
    signature_data = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Nouveaux champs pour les signatures dessinées
    drawn_signature = models.TextField(blank=True, null=True)  # Stockage de l'image en base64
    signature_position_x = models.FloatField(null=True, blank=True)
    signature_position_y = models.FloatField(null=True, blank=True)
    signature_page = models.IntegerField(null=True, blank=True, default=1)
    
    # Référence à une signature enregistrée (si utilisée)
    saved_signature = models.ForeignKey('SavedSignature', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_signatures')

    def __str__(self):
        return f"Signature de {self.signer.email} pour {self.document.id}"

class SavedSignature(models.Model):
    """
    Modèle pour stocker les signatures des utilisateurs de manière sécurisée.
    La signature est chiffrée avant d'être stockée dans la base de données.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_signatures')
    name = models.CharField(_('Nom de la signature'), max_length=100)
    signature_data = models.TextField(_('Données de signature chiffrées'))
    is_default = models.BooleanField(_('Signature par défaut'), default=False)
    created_at = models.DateTimeField(_('Date de création'), auto_now_add=True)
    last_used_at = models.DateTimeField(_('Dernière utilisation'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('Signature enregistrée')
        verbose_name_plural = _('Signatures enregistrées')
        ordering = ['-is_default', '-last_used_at', '-created_at']
        unique_together = [['user', 'name']]
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    def save(self, *args, **kwargs):
        # Si cette signature est définie comme par défaut, désactiver les autres signatures par défaut
        if self.is_default:
            SavedSignature.objects.filter(user=self.user, is_default=True).update(is_default=False)
        
        # Si c'est une nouvelle signature et qu'il n'y a pas d'autres signatures, la définir comme par défaut
        if not self.pk and not SavedSignature.objects.filter(user=self.user).exists():
            self.is_default = True
        
        # Chiffrer la signature si elle n'est pas déjà chiffrée
        if not self.pk or kwargs.pop('update_signature', False):
            self.encrypt_signature()
        
        super().save(*args, **kwargs)
    
    def encrypt_signature(self):
        """Chiffre les données de signature avant de les stocker"""
        if not hasattr(settings, 'SIGNATURE_ENCRYPTION_KEY'):
            raise ValidationError(_("Clé de chiffrement non configurée"))
        
        # S'assurer que la clé est propre (sans espaces)
        key = settings.SIGNATURE_ENCRYPTION_KEY.strip().encode()
        
        try:
            # Vérifier si les données sont déjà chiffrées (commencent par gAAAAA)
            if isinstance(self.signature_data, str) and not self.signature_data.startswith('gAAAAA'):
                print(f"DEBUG - Chiffrement des données de signature pour {self.name}")
                # S'assurer que les données sont propres
                clean_data = self.signature_data.strip()
                f = Fernet(key)
                encrypted_data = f.encrypt(clean_data.encode())
                self.signature_data = encrypted_data.decode()
                print(f"DEBUG - Signature chiffrée avec succès: {self.signature_data[:50]}...")
            elif isinstance(self.signature_data, str) and self.signature_data.startswith('gAAAAA'):
                print(f"DEBUG - Les données sont déjà chiffrées pour {self.name}")
        except Exception as e:
            print(f"DEBUG - Erreur lors du chiffrement: {str(e)}")
            raise ValidationError(_(f"Erreur lors du chiffrement: {str(e)}"))
    
    def decrypt_signature(self):
        """Déchiffre les données de signature pour utilisation"""
        if not hasattr(settings, 'SIGNATURE_ENCRYPTION_KEY'):
            raise ValidationError(_("Clé de chiffrement non configurée"))
        
        # Vérifier si les données sont chiffrées
        if not self.signature_data.startswith('gAAAAA'):
            print(f"DEBUG - Les données ne sont pas chiffrées pour {self.name}, retour des données brutes")
            return self.signature_data
        
        # S'assurer que la clé est propre (sans espaces)
        key = settings.SIGNATURE_ENCRYPTION_KEY.strip().encode()
        print(f"DEBUG - Longueur de la clé: {len(key)} bytes")
        print(f"DEBUG - Clé: {key}")
        
        try:
            # S'assurer que les données de signature sont propres
            signature_data = self.signature_data.strip()
            print(f"DEBUG - Signature data: {signature_data[:50]}...")
            
            f = Fernet(key)
            decrypted_data = f.decrypt(signature_data.encode())
            return decrypted_data.decode()
        except Exception as e:
            print(f"DEBUG - Erreur de déchiffrement: {str(e)}")
            print(f"DEBUG - Type de signature_data: {type(self.signature_data)}")
            print(f"DEBUG - Longueur de signature_data: {len(self.signature_data)}")
            
            # Essayer de diagnostiquer le problème
            if len(key) != 32 and not key.endswith(b'='):
                print("DEBUG - La clé n'est pas au format base64 valide")
            
            if not self.signature_data.startswith('gAAAAA'):
                print("DEBUG - Les données de signature ne semblent pas être au format Fernet")
            
            raise ValidationError(_(f"Erreur lors du déchiffrement: {str(e)}"))
    
    def mark_as_used(self):
        """Marque la signature comme utilisée récemment"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])

class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    file = models.FileField(
        upload_to='documents/',
        validators=[validate_file_type]
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('signed', 'Signed')],
        default='pending'
    )
    hash = models.CharField(max_length=64, unique=True, blank=True)
    signatures = models.ManyToManyField(Signature, related_name="documents")
    

    class Meta:
        permissions = [
            ("can_sign_document", "Can sign document"),
            ("can_view_document", "Can view document"),
        ]
        constraints = [ 
            models.UniqueConstraint(fields=['hash'], name='unique_document_hash')
        ]

    def save(self, *args, **kwargs):
        # Generate hash based on file content if not already set
        if not self.hash and self.file:
            self.file.seek(0)  # Ensure we read the file from the beginning
            self.hash = hashlib.sha256(self.file.read()).hexdigest()
            self.file.seek(0)  # Reset file pointer after reading
        super().save(*args, **kwargs)

    def can_be_signed_by(self, user):
        return (
            self.uploaded_by == user or
            self.signatures.filter(signer=user).exists()
        )

    
    
    # Subucrip
    def pre_sign_check(self, user):
        """Vérifie si l'utilisateur peut signer ce document selon son forfait"""
        try:
            subscription = user.subscription
            
            # Vérifier le quota de signatures
            if not subscription.can_sign_more:
                return False, "Vous avez atteint votre limite de signatures pour ce mois"
            
            # Vérifier le nombre de signataires autorisés
            signers_count = self.signers.count()
            if subscription.plan.max_signers > 0 and signers_count > subscription.plan.max_signers:
                return False, f"Votre forfait permet un maximum de {subscription.plan.max_signers} signataires"
            
            return True, ""
            
        except Subscription.DoesNotExist:
            return False, "Aucun forfait actif trouvé"
    
    def post_sign_update(self, user):
        """Met à jour les compteurs après une signature"""
        try:
            subscription = user.subscription
            subscription.signatures_used += 1
            subscription.save(update_fields=['signatures_used'])
        except Subscription.DoesNotExist:
            pass
    def __str__(self):
        return self.title

class DocumentSigner(models.Model):
    """
    Modèle pour gérer les signataires invités pour un document
    """
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('signed', 'Signé'),
        ('rejected', 'Refusé'),
        ('expired', 'Expiré'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='signers')
    # Peut être un utilisateur existant ou un utilisateur invité
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents_to_sign', null=True, blank=True)
    email = models.EmailField()
    full_name = models.CharField(max_length=255)
    # Token unique pour accéder au document à signer
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    invitation_sent_at = models.DateTimeField(auto_now_add=True)
    invitation_expires_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.IntegerField(default=0)
    # Position de la signature sur le document
    signature_position_x = models.FloatField(null=True, blank=True)
    signature_position_y = models.FloatField(null=True, blank=True)
    signature_page = models.IntegerField(default=1)
    # Messages et notes
    message = models.TextField(blank=True, null=True)  # Message envoyé à l'invité
    notes = models.TextField(blank=True, null=True)  # Notes internes
    # Si l'invitation a créé un nouvel utilisateur
    created_user = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = _('Signataire de document')
        verbose_name_plural = _('Signataires de document')
        unique_together = [['document', 'email']]
    
    def __str__(self):
        return f"{self.full_name} ({self.email}) - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Définir une date d'expiration par défaut (14 jours)
        if not self.invitation_expires_at:
            self.invitation_expires_at = timezone.now() + timezone.timedelta(days=14)
        
        # Si l'email correspond à un utilisateur existant, associer l'utilisateur
        if not self.user:
            try:
                self.user = User.objects.get(email=self.email)
            except User.DoesNotExist:
                pass
                
        super().save(*args, **kwargs)
    
    def send_invitation(self):
        """Envoyer une invitation par email au signataire"""
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        
        subject = f"Invitation à signer un document : {self.document.title}"
        
        # URL de signature avec le token
        sign_url = f"{settings.FRONTEND_URL}/documents/{self.token}/"
        sign_url = f"{settings.FRONTEND_URL}/documents/{self.document.id}/invite"
        # Préparer le contexte pour le template
        context = {
            'full_name': self.full_name,
            'document_title': self.document.title,
            'sender_name': self.document.uploaded_by.get_full_name() or self.document.uploaded_by.email,
            'sign_url': sign_url,
            'expiry_date': self.invitation_expires_at.strftime('%d/%m/%Y'),
            'custom_message': self.message,
        }
        
        # Rendre le template HTML
        html_message = render_to_string('documents/email_invitation.html', context)
        plain_message = strip_tags(html_message)  # Version texte brut pour les clients mail sans HTML
        
        # Envoyer l'email en utilisant la fonction d'envoi de notification
        send_notification_email(subject, plain_message, [self.email], html_message=html_message)
        
        # Mettre à jour la date d'envoi
        self.invitation_sent_at = timezone.now()
        self.save(update_fields=['invitation_sent_at'])
        return True
    
    def send_reminder(self):
        """Envoyer un rappel au signataire"""
        if self.status != 'pending':
            return False
        
        subject = f"Rappel : Document en attente de signature - {self.document.title}"
        
        # URL de signature avec le token
        sign_url = f"{settings.FRONTEND_URL}/documents/{self.token}/sign"
        
        message = f"""
        Bonjour {self.full_name},
        
        Ceci est un rappel concernant le document "{self.document.title}" qui est toujours en attente de votre signature.
        
        Pour consulter et signer ce document, veuillez cliquer sur le lien suivant:
        {sign_url}
        
        Ce lien expirera le {self.invitation_expires_at.strftime('%d/%m/%Y')}.
        
        Si vous avez des questions, n'hésitez pas à contacter la personne qui vous a envoyé ce document.
        
        Cordialement,
        L'équipe Wolof Sign
        """
        
        send_notification_email(subject, message, [self.email])
        
        # Mettre à jour le compteur de rappel
        self.reminder_count += 1
        self.reminder_sent_at = timezone.now()
        self.save(update_fields=['reminder_count', 'reminder_sent_at'])
        return True
    
    def is_expired(self):
        """Vérifie si l'invitation a expiré"""
        return self.invitation_expires_at and self.invitation_expires_at < timezone.now()
    
    def mark_as_signed(self, signature_id=None):
        """Marquer comme signé"""
        self.status = 'signed'
        self.signed_at = timezone.now()
        self.save(update_fields=['status', 'signed_at'])
    
    def mark_as_rejected(self):
        """Marquer comme refusé"""
        self.status = 'rejected'
        self.save(update_fields=['status'])
