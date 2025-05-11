from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
# router.register(r'signatures', SignatureViewSet, basename='signature')  # Cette vue n'est pas définie
router.register(r'saved-signatures', SavedSignatureViewSet, basename='saved-signature')

# Routes imbriquées pour les signataires d'un document spécifique
document_signers_router = DefaultRouter()
document_signers_router.register(r'signers', DocumentSignerViewSet, basename='document-signer')

urlpatterns = [
    path('', include(router.urls)),
    # Routes imbriquées pour les signataires d'un document
    path('documents/<uuid:document_id>/', include([
        path('signers/', DocumentSignerViewSet.as_view({'get': 'list', 'post': 'create'})),
        path('signers/<uuid:pk>/', DocumentSignerViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        })),
        path('sign_pdf_with_token/', DocumentSignerViewSet.as_view({'post': 'sign_pdf_with_token'})),
    ])),
]