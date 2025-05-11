from django.db import models
import uuid
from users.models import User

class Certificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    public_key = models.TextField()
    private_key = models.TextField()
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('revoked', 'Revoked'), ('expired', 'Expired')],
        default='active'
    )
    revocation_reason = models.TextField(blank=True)
    # def clean(self):
    #     if self.valid_until <= self.valid_from:
    #         raise ValidationError("`valid_until` doit être supérieur à `valid_from`.")

    def __str__(self):
        return f"Certificate for {self.user.email}"
    
