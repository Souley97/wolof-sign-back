from rest_framework import serializers
from .models import Document, Signature, SavedSignature, DocumentSigner
from users.serializers import UserSerializer
from certificates.serializers import CertificateSerializer
from django.contrib.auth import get_user_model
import collections

User = get_user_model()

class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by = UserSerializer(read_only=True)
    signatures = serializers.SerializerMethodField()
    certificate = CertificateSerializer(read_only=True)

    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'uploaded_by', 'created_at', 'status', 'signatures', 'certificate']
        read_only_fields = ['hash', 'status', 'certificate']

    def get_signatures(self, obj):
        if isinstance(obj, collections.OrderedDict):
            print("obj", obj)
            # Lors d'un POST, les signatures ne sont pas encore associées
            return []
        else:
            # Lors d'un GET, récupérez les signatures associées
            return SignatureSerializer(obj.signature_set.all(), many=True).data
        return []

class SignatureSerializer(serializers.ModelSerializer):
    signer = UserSerializer(read_only=True)
    certificate = CertificateSerializer(read_only=True)
    signature_data = serializers.CharField()

    class Meta:
        model = Signature
        fields = ['id', 'document', 'signer', 'certificate', 'signature_data', 'drawn_signature', 'signature_position_x', 'signature_position_y', 'signature_page']
        read_only_fields = ['signature_data']

class SignatureDessinSerializer(serializers.ModelSerializer):
    signature = serializers.CharField()  # Base64 de l'image de signature
    position = serializers.DictField(
        child=serializers.IntegerField()
    )

    class Meta:
        model = Signature
        fields = ['id', 'document','position', 'signer', 'certificate', 'signature_data', 'drawn_signature', 'signature_position_x', 'signature_position_y', 'signature_page']
        read_only_fields = ['signature_data']    

    def validate_position(self, value):
        required_keys = ['x', 'y', 'page']
        for key in required_keys:
            if key not in value:
                raise serializers.ValidationError(f"La clé '{key}' est requise dans la position")
        return value 
    
class SavedSignatureSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    signature_data = serializers.CharField(write_only=True)  # Écriture uniquement pour la sécurité
    
    class Meta:
        model = SavedSignature
        fields = ['id', 'user', 'name', 'signature_data', 'is_default', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'user', 'created_at', 'last_used_at']
    
    def create(self, validated_data):
        # Associer l'utilisateur actuel à la signature
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)

class SavedSignatureListSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la liste des signatures sauvegardées (sans les données sensibles)"""
    class Meta:
        model = SavedSignature
        fields = ['id', 'name', 'is_default', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'created_at', 'last_used_at']

class DocumentSignerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    document = DocumentSerializer(read_only=True)  # Inclut tous les champs du document

    class Meta:
        model = DocumentSigner
        fields = '__all__'
class DocumentSignerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentSigner
        fields = ['email', 'full_name', 'message', 'notes', 'signature_position_x', 
                 'signature_position_y', 'signature_page', 'invitation_expires_at']
    
    def validate_email(self, value):
        """Valider que l'email est unique pour ce document"""
        document = self.context.get('document')
        if document and DocumentSigner.objects.filter(document=document, email=value).exists():
            raise serializers.ValidationError("Ce signataire a déjà été invité pour ce document.")
        return value

class DocumentWithSignersSerializer(DocumentSerializer):
    signers = DocumentSignerSerializer(many=True, read_only=True)
    
    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ['signers']