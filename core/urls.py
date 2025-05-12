from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from certificates.views import CertificateViewSet
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

router = DefaultRouter()
router.register(r'certificates', CertificateViewSet, basename='certificate')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/', include('documents.urls')),
    path('api/user/', include('users.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # Servir les fichiers média également en production
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]

# En mode développement uniquement, utiliser la méthode standard de Django
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)