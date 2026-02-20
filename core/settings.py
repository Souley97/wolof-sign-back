import os
from pathlib import Path
import environ
from datetime import timedelta
from cryptography.fernet import Fernet
import logging
import dj_database_url

logger = logging.getLogger(__name__)

# Configurer environ
env = environ.Env()
env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
environ.Env.read_env(env_file)

BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', False)
# ALLOWED_HOSTS: utilise DJANGO_ALLOWED_HOSTS ou ALLOWED_HOSTS du .env
_default_hosts = 'localhost,127.0.0.1,sign.wolofdigital.com,www.sign.wolofdigital.com,apisign.wolofdigital.com'
_allowed = os.getenv('DJANGO_ALLOWED_HOSTS') or os.getenv('ALLOWED_HOSTS') or _default_hosts
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(',') if h.strip()]

# Security Headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Disable SSL redirect in development
SECURE_SSL_REDIRECT = False  # Set to True only in production

# Only enable these security settings in production
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
else:
    # In development, disable these security features
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    SECURE_BROWSER_XSS_FILTER = False
    SECURE_CONTENT_TYPE_NOSNIFF = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

X_FRAME_OPTIONS = 'DENY'

ROOT_URLCONF = 'core.urls'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.User'

# Rate Limiting
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'auth': '30/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=120),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': 'HS512',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# CORS Settings
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://sign.wolofdigital.com',
    'https://www.sign.wolofdigital.com',
    'https://apisign.wolofdigital.com',
])
CORS_ALLOW_CREDENTIALS = True

# Additional CORS settings to fix preflight issues
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all origins in development
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'users',
    'documents',
    'certificates',
    'subscriptions',
]
# monprojet/settings.py

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Assurez-vous que ce chemin est correct
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'core.middleware.OptionsMiddleware',  # Custom middleware to handle OPTIONS requests
    'core.middleware.MediaFilesMiddleware',  # Middleware pour gérer les en-têtes des fichiers média
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases
# DATABASE_URL = "postgresql://postgres:AGoHKPfINFzJWzwankCiGExwGtEpRyoO@switchback.proxy.rlwy.net:51653/railway"
# DATABASES = {
    
#     "default": dj_database_url.config(default=DATABASE_URL, conn_max_age=1800),
# }

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', 'sqlite:///daata.db'),
        conn_max_age=600
    )
}


# DATABASES = {
#     'default': {
#         # 'ENGINE': 'django.db.backends.sqlite3',
#         # 'NAME': BASE_DIR / 'db.sqlite3',
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'wolof_sign',
#         'USER': 'postgres',
#         'PASSWORD': 'Bamsachine97',
#         'HOST': 'localhost',
#         'PORT': '5432',  
#     }
# }

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_DIRS = [
#     BASE_DIR / 'static',
# ]

# Media files (Uploaded by users)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# S'assurer que les répertoires existent
os.makedirs(STATIC_ROOT, exist_ok=True)
os.makedirs(MEDIA_ROOT, exist_ok=True)

# Configuration pour le stockage des fichiers en production
if not DEBUG:
    # Si AWS S3 ou un autre service de stockage est configuré, utilisez-le ici
    # Sinon, assurez-vous que les fichiers peuvent être servis directement depuis le serveur
    pass
    # Exemple pour AWS S3 (à décommenter et configurer si nécessaire):
    # AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
    # AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
    # AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', default='')
    # AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    # AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    # AWS_DEFAULT_ACL = 'public-read'
    # AWS_LOCATION = 'media'
    # DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Email Configuration
if DEBUG:
    # En mode développement, utiliser le backend console pour afficher les emails dans la console
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    logger.info("Using console email backend for development")
else:
    # En production, utiliser SMTP avec Gmail
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
    
    # Vérification de la configuration email
    if not all([EMAIL_HOST_USER, EMAIL_HOST_PASSWORD]):
        logger.warning("Email configuration is incomplete. Please check your environment variables.")
    
    # Configuration supplémentaire pour la sécurité
    EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
    EMAIL_TIMEOUT = env.int('EMAIL_TIMEOUT', default=30)  # Timeout en secondes
    EMAIL_SSL_CERTVERIFY = env.bool('EMAIL_SSL_CERTVERIFY', default=True)

# Clé de chiffrement pour les signatures
# En production, cette clé doit être stockée de manière sécurisée (variables d'environnement)
SIGNATURE_ENCRYPTION_KEY = env('SIGNATURE_ENCRYPTION_KEY', default=None)
if SIGNATURE_ENCRYPTION_KEY:
    # Nettoyer la clé (supprimer les espaces)
    SIGNATURE_ENCRYPTION_KEY = SIGNATURE_ENCRYPTION_KEY.strip()

# Si la clé n'est pas définie ou n'est pas au format attendu, générer une nouvelle clé
try:
    if SIGNATURE_ENCRYPTION_KEY:
        # Tester si la clé est valide
        key_bytes = SIGNATURE_ENCRYPTION_KEY.encode()
        Fernet(key_bytes)
    else:
        raise ValueError("Clé non définie")
except Exception as e:
    logger.warning(f"ATTENTION: La clé de chiffrement n'est pas valide ({str(e)}). Génération d'une nouvelle clé temporaire.")
    SIGNATURE_ENCRYPTION_KEY = Fernet.generate_key().decode()

# Stripe Configuration
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
STRIPE_SUCCESS_URL = os.environ.get('STRIPE_SUCCESS_URL', 'http://localhost:3000/dashboard/subscription?status=success')
STRIPE_CANCEL_URL = os.environ.get('STRIPE_CANCEL_URL', 'http://localhost:3000/pricing?status=canceled')

# PayDunya Configuration
PAYDUNYA_MASTER_KEY = os.environ.get('PAYDUNYA_MASTER_KEY', '')
PAYDUNYA_PRIVATE_KEY = os.environ.get('PAYDUNYA_PRIVATE_KEY', '')
PAYDUNYA_PUBLIC_KEY = os.environ.get('PAYDUNYA_PUBLIC_KEY', '')
PAYDUNYA_TOKEN = os.environ.get('PAYDUNYA_TOKEN', '')

# Fix key mismatch between test and live environments
if 'test_' in PAYDUNYA_PRIVATE_KEY and not PAYDUNYA_MASTER_KEY.startswith('test_'):
    # We're using test private key but have a live master key - force test mode
    # The correct solution is to update your .env file with matching keys
    # This is a temporary fix for development
    PAYDUNYA_MASTER_KEY = 'BPuaGe7s-X4mG-983H-ciPz-Yi5KlKgdQaSf'  # Example test master key - REPLACE THIS

# Ensure TOKEN is set for test environment
if 'test_' in PAYDUNYA_PRIVATE_KEY and not PAYDUNYA_TOKEN:
    PAYDUNYA_TOKEN = 'test_token_iFLGF46JfTFsYy1p2aECz6XPnDk'  # Example test token - REPLACE IF NEEDED

PAYDUNYA_BASE_URL = os.environ.get('PAYDUNYA_BASE_URL', 'https://app.paydunya.com/api/v1')
PAYDUNYA_TEST_MODE = os.environ.get('PAYDUNYA_TEST_MODE', 'True').lower() == 'true'
PAYDUNYA_SUCCESS_URL = os.environ.get('PAYDUNYA_SUCCESS_URL', STRIPE_SUCCESS_URL)
PAYDUNYA_CANCEL_URL = os.environ.get('PAYDUNYA_CANCEL_URL', STRIPE_CANCEL_URL)

# Store Information (for PayDunya)
STORE_NAME = os.environ.get('STORE_NAME', 'Wolof Sign')
STORE_TAGLINE = os.environ.get('STORE_TAGLINE', 'Signature électronique en toute simplicité')
STORE_PHONE = os.environ.get('STORE_PHONE', '+221 XX XXX XX XX')
STORE_ADDRESS = os.environ.get('STORE_ADDRESS', 'Dakar, Sénégal')

# Fonction pour créer les produits et prix dans Stripe
def create_stripe_products():
    import stripe
    from subscriptions.models import Plan
    
    stripe.api_key = STRIPE_SECRET_KEY
    
    # Créer ou mettre à jour les plans dans Stripe
    plans = Plan.objects.all()
    for plan in plans:
        if plan.plan_type == 'decouverte':
            continue  # Ignorer le plan gratuit
        
        # Créer le produit s'il n'existe pas encore
        if not hasattr(plan, 'stripe_product_id') or not plan.stripe_product_id:
            product = stripe.Product.create(
                name=plan.name,
                description=plan.description,
                metadata={'plan_id': plan.id, 'plan_type': plan.plan_type}
            )
            plan.stripe_product_id = product.id
        
        # Créer ou mettre à jour les prix
        if not plan.stripe_price_id_monthly:
            price_monthly = stripe.Price.create(
                product=plan.stripe_product_id,
                # unit_amount=int(plan.price_monthly ),  # En centimes
                unit_amount=int(plan.price_monthly ),  # En centimes
                currency='xof',  # Franc CFA
                recurring={'interval': 'month'},
                metadata={'plan_id': plan.id, 'billing_cycle': 'monthly'}
            )
            plan.stripe_price_id_monthly = price_monthly.id
        
        if not plan.stripe_price_id_annually:
            price_annually = stripe.Price.create(
                product=plan.stripe_product_id,
                # unit_amount=int(plan.price_annually ),  # En centimes
                unit_amount=int(plan.price_annually ),  # En centimes
                currency='xof',  # Franc CFA
                recurring={'interval': 'year'},
                metadata={'plan_id': plan.id, 'billing_cycle': 'annually'}
            )
            plan.stripe_price_id_annually = price_annually.id
        
        plan.save()
