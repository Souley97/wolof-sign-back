from rest_framework import serializers
from .models import Plan, Subscription, PaymentHistory
from django.contrib.auth import get_user_model

User = get_user_model()

class UserMinSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username']

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'
    
    def validate(self, data):
        """Valider que le prix annuel est inférieur au prix mensuel x 12"""
        if 'price_monthly' in data and 'price_annually' in data:
            if data['price_annually'] > data['price_monthly'] * 12:
                raise serializers.ValidationError("Le prix annuel ne devrait pas dépasser 12 fois le prix mensuel")
        return data

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    user = UserMinSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.all(), 
        source='plan',
        write_only=True
    )
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True
    )
    remaining_signatures = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'user_id', 'plan', 'plan_id', 'status', 'billing_cycle',
            'stripe_customer_id', 'stripe_subscription_id', 'start_date',
            'current_period_end', 'canceled_at', 'custom_max_signatures',
            'custom_storage_limit', 'signatures_used', 'storage_used',
            'remaining_signatures', 'created_at', 'updated_at'
        ]
    
    def validate(self, data):
        """Valider que la date de fin est après la date de début"""
        if 'start_date' in data and 'current_period_end' in data:
            if data['current_period_end'] <= data['start_date']:
                raise serializers.ValidationError(
                    "La date de fin de période doit être postérieure à la date de début"
                )
        return data

class PaymentHistorySerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer(read_only=True)
    subscription_id = serializers.PrimaryKeyRelatedField(
        queryset=Subscription.objects.all(),
        source='subscription',
        write_only=True
    )
    
    class Meta:
        model = PaymentHistory
        fields = [
            'id', 'subscription', 'subscription_id', 'amount', 'payment_date',
            'stripe_invoice_id', 'stripe_payment_intent_id', 'status', 'payment_method'
        ]

class SubscriptionUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les mises à jour partielles d'abonnement"""
    
    class Meta:
        model = Subscription
        fields = [
            'plan', 'status', 'billing_cycle', 'current_period_end',
            'custom_max_signatures', 'custom_storage_limit', 'signatures_used',
            'storage_used'
        ]

class PlanUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les mises à jour partielles de plan"""
    
    class Meta:
        model = Plan
        fields = [
            'name', 'description', 'is_active', 'max_signatures', 'max_signers',
            'storage_limit', 'retention_days', 'has_api_access', 'support_level',
            'price_monthly', 'price_annually', 'stripe_price_id_monthly',
            'stripe_price_id_annually'
        ]

class SubscriptionAdminSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour l'administration des abonnements"""
    plan = PlanSerializer(read_only=True)
    user = UserMinSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.all(), 
        source='plan',
        write_only=True
    )
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True
    )
    remaining_signatures = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Subscription
        fields = '__all__'
        
