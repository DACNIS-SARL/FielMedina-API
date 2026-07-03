from django.db import models
from django.utils.translation import gettext_lazy as _
from shared.models import UserProfile
from guard.models import Event, Ad

class TransactionType(models.TextChoices):
    SUBSCRIPTION = 'subscription', _('Subscription')
    EVENT_BOOST = 'event_boost', _('Event Boost')
    AD_BOOST = 'ad_boost', _('Ad Boost')

class TransactionStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    VALIDATED = 'validated', _('Validated')
    REJECTED = 'rejected', _('Rejected')
    CANCELED = 'canceled', _('Canceled')

class PaymentTransaction(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='transactions', verbose_name=_("User Profile"))
    transaction_type = models.CharField(max_length=32, choices=TransactionType.choices, verbose_name=_("Transaction Type"))
    status = models.CharField(max_length=32, choices=TransactionStatus.choices, default=TransactionStatus.PENDING, verbose_name=_("Status"))
    
    # Context
    months = models.IntegerField(null=True, blank=True, verbose_name=_("Subscription Months"))
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions', verbose_name=_("Event"))
    ad = models.ForeignKey(Ad, null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions', verbose_name=_("Ad"))
    ad_start_date = models.DateField(null=True, blank=True, verbose_name=_("Ad Start Date"))
    ad_end_date = models.DateField(null=True, blank=True, verbose_name=_("Ad End Date"))
    
    # Financials
    amount_ht = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Amount HT"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Tax Amount (19%)"))
    timbre_fiscal = models.DecimalField(max_digits=10, decimal_places=2, default=1.00, verbose_name=_("Timbre Fiscal"))
    total_ttc = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Total TTC"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    validated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Validated At"))

    class Meta:
        verbose_name = _("Payment Transaction")
        verbose_name_plural = _("Payment Transactions")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.user} - {self.get_status_display()}"

    @property
    def reference(self):
        if self.transaction_type == TransactionType.SUBSCRIPTION:
            prefix = "ORDER-SUB"
        elif self.transaction_type == TransactionType.AD_BOOST:
            prefix = "ORDER-ADS"
        elif self.transaction_type == TransactionType.EVENT_BOOST:
            prefix = "ORDER-EVN"
        else:
            prefix = "ORDER-GEN"
        return f"{prefix}-{self.id}"

    @property
    def is_stale(self):
        from django.utils import timezone
        import datetime
        return self.status == TransactionStatus.PENDING and self.created_at < timezone.now() - datetime.timedelta(days=5)
