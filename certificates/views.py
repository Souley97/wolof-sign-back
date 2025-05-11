from datetime import datetime
from django.utils.timezone import now, make_aware
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Certificate
from .serializers import CertificateSerializer
from .utils import generate_key_pair

class CertificateViewSet(viewsets.ModelViewSet):
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Certificate.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def generate(self, request):
        public_key, private_key = generate_key_pair()
        valid_until = request.data.get('valid_until')

        if not valid_until:
            return Response({'error': '`valid_until` est requis.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Convertir `valid_until` en un objet datetime
        try:
            valid_until = datetime.fromisoformat(valid_until)
        except ValueError:
            return Response({'error': '`valid_until` est dans un format invalide. Utilisez le format ISO 8601.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Rendre `valid_until` "aware" en ajoutant un fuseau horaire si nécessaire
        if valid_until.tzinfo is None:
            valid_until = make_aware(valid_until)

        # Comparer avec `now`
        if valid_until <= now():
            return Response({'error': '`valid_until` doit être dans le futur.'}, status=status.HTTP_400_BAD_REQUEST)
        
        certificate = Certificate.objects.create(
            user=request.user,
            public_key=public_key,
            private_key=private_key,
            valid_until=valid_until
        )
        return Response(CertificateSerializer(certificate).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        certificate = self.get_object()
        certificate.status = 'revoked'
        certificate.revocation_reason = request.data.get('reason', '')
        certificate.save()
        return Response(CertificateSerializer(certificate).data)
