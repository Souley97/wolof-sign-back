from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Plan(models.Model):
    """Modèle pour les plans d'abonnement"""
    PLAN_TYPES = (
        ('decouverte', 'Découverte'),
        ('professionnel', 'Professionnel'),
        ('entreprise', 'Entreprise'),
        ('gouvernement', 'Gouvernement'),
    )
    
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_annually = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_signatures = models.IntegerField(default=0)  # 0 = illimité
    max_signers = models.IntegerField(default=1)  # Par document
    storage_limit = models.IntegerField(default=100)  # En Mo, 0 = illimité
    retention_days = models.IntegerField(default=30)  # Durée de conservation des documents signés
    has_api_access = models.BooleanField(default=False)
    support_level = models.CharField(max_length=50, default='email')
    is_active = models.BooleanField(default=True)
    
    # Champs Stripe
    stripe_product_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id_annually = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"

class Subscription(models.Model):
    """Modèle pour les abonnements utilisateur"""
    STATUS_CHOICES = (
        ('active', 'Actif'),
        ('trialing', 'Période d\'essai'),
        ('past_due', 'Paiement en retard'),
        ('canceled', 'Annulé'),
        ('unpaid', 'Impayé'),
    )
    
    BILLING_CYCLE_CHOICES = (
        ('monthly', 'Mensuel'),
        ('annually', 'Annuel'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default='monthly')
    start_date = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    
    # Utilisation
    signatures_used = models.IntegerField(default=0)
    storage_used = models.IntegerField(default=0)  # En Mo
    
    # Limites personnalisées (remplacent celles du plan si définies)
    custom_max_signatures = models.IntegerField(default=5)
    custom_storage_limit = models.IntegerField(null=True, blank=True)
    
    # Champs Stripe
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def remaining_signatures(self):
        """Retourne le nombre de signatures restantes dans le forfait"""
        max_signatures = self.custom_max_signatures or self.plan.max_signatures
        if max_signatures <= 0:  # Illimité
            return -1
        return max(0, max_signatures - self.signatures_used)
    
    @property
    def has_unlimited_signatures(self):
        """Vérifie si l'abonnement a des signatures illimitées"""
        max_signatures = self.custom_max_signatures or self.plan.max_signatures
        return max_signatures <= 0
    
    @property
    def is_active(self):
        """Vérifie si l'abonnement est actif"""
        return self.status in ['active', 'trialing'] and (
            self.current_period_end is None or 
            self.current_period_end > timezone.now()
        )
    
    def can_sign(self):
        """Vérifie si l'utilisateur peut signer un document"""
        if not self.is_active:
            return False
        
        # Vérifier la limite de signatures
        if not self.has_unlimited_signatures and self.remaining_signatures <= 0:
            return False
            
        return True
    
    def increment_signature_count(self):
        """Incrémente le compteur de signatures"""
        self.signatures_used += 1
        self.save(update_fields=['signatures_used'])
    
    def update_storage_used(self, file_size_mb):
        """Met à jour l'espace de stockage utilisé"""
        self.storage_used += file_size_mb
        self.save(update_fields=['storage_used'])
    
    def reset_usage_counters(self):
        """Réinitialise les compteurs d'utilisation"""
        self.signatures_used = 0
        self.storage_used = 0
        self.save(update_fields=['signatures_used', 'storage_used'])
    
    def __str__(self):
        return f"Abonnement de {self.user.email} - {self.plan.name}"

class PaymentHistory(models.Model):
    """Historique des paiements"""
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('paid', 'Payé'),
        ('failed', 'Échoué'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('card', 'Carte bancaire'),
        ('mobile_money', 'Mobile Money'),
    )
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='card')
    
    # Identifiants Stripe
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Identifiants PayDunya
    paydunya_token = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Paiement de {self.amount} {self.get_status_display()} pour {self.subscription.user.email}"
