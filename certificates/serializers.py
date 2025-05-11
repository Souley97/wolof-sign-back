# certificates/serializers.py
from rest_framework import serializers
from .models import Certificate

class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        # fields = '__all__'
        exclude = ['private_key']  # Masquer la clé privée pour les utilisateurs.

