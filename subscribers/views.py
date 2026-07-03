from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.utils import timezone
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
import datetime

from django.core.mail import send_mail
from django.conf import settings

from .models import PaymentTransaction, TransactionType, TransactionStatus
from guard.models import Event, Ad

def send_transaction_emails(transaction):
    client_email = transaction.user.user.email
    admin_emails = settings.ADMIN_LIST_EMAILS
    
    # Send to client
    if client_email:
        subject_client = _("FielMedina - Bank Transfer Instructions")
        message_client = _("""Hello {user_name},

Your request for {transaction_type} has been received!

Total Amount due: {total} TND

Please complete the payment via bank transfer using the details below:
Account Name: DACNIS SARL
Bank: BIAT
RIB: 08129030011000676770
IBAN: TN5908129030011000676770

IMPORTANT: Please include this reference in your bank transfer motif/object: {reference}

We must receive the amount within 3 working days, or your order will be canceled.

Once the transfer is done, please reply to this email (commercial@dacnis.tn) with your proof of payment so we can validate your transaction.

Thank you,
The FielMedina Team""").format(
            user_name=transaction.user.user.get_full_name() or transaction.user.user.username,
            transaction_type=transaction.get_transaction_type_display(),
            total=transaction.total_ttc,
            reference=transaction.reference
        )
        send_mail(subject_client, message_client, settings.DEFAULT_FROM_EMAIL, [client_email], fail_silently=True)

    # Send to admin
    subject_admin = _("New Pending Payment: {transaction_type}").format(transaction_type=transaction.get_transaction_type_display())
    message_admin = _("""A new offline bank transfer request has been submitted.

Client: {client_email}
Type: {transaction_type}
Amount: {total} TND

Please check the FielMedina Admin Validation panel to verify their proof of payment and approve the transaction.""").format(
        client_email=client_email or transaction.user.user.username,
        transaction_type=transaction.get_transaction_type_display(),
        total=transaction.total_ttc
    )
    send_mail(subject_admin, message_admin, settings.DEFAULT_FROM_EMAIL, admin_emails, fail_silently=True)

def send_cancellation_email(transaction):
    client_email = transaction.user.user.email
    if client_email:
        subject = _("FielMedina - Order Canceled")
        message = _("""Hello {user_name},

Your order for {transaction_type} ({reference}) has been canceled because no money was received within 5 working days.

If you have already made the transfer, please contact us immediately at commercial@dacnis.tn with your proof of payment.

Thank you,
The FielMedina Team""").format(
            user_name=transaction.user.user.get_full_name() or transaction.user.user.username,
            transaction_type=transaction.get_transaction_type_display(),
            reference=transaction.reference
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client_email], fail_silently=True)

def send_validation_email(transaction):
    client_email = transaction.user.user.email
    if client_email:
        subject = _("FielMedina - Payment Validated")
        message = _("""Hello {user_name},

Great news! Your payment for {transaction_type} has been validated by our team.
Your service is now active. We will send you an invoice shortly.

Thank you,
The FielMedina Team""").format(
            user_name=transaction.user.user.get_full_name() or transaction.user.user.username,
            transaction_type=transaction.get_transaction_type_display()
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client_email], fail_silently=True)


# -----------------------------------------------------------------------------
# Mixins
# -----------------------------------------------------------------------------
class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and getattr(self.request.user.profile, 'is_staff_type', False)

# -----------------------------------------------------------------------------
# Client Views
# -----------------------------------------------------------------------------
class PaymentPortalView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, 'guard/views/subscribers/payment_portal.html')

    def post(self, request):
        months = int(request.POST.get('months', 1))
        
        # Calculate totals
        rates = {1: 19.0, 3: 55.0, 6: 110.0, 12: 150.0}
        amount_ht = rates.get(months, 19.0)
        tax_amount = amount_ht * 0.19
        timbre = 1.0
        total = amount_ht + tax_amount + timbre

        transaction = PaymentTransaction.objects.create(
            user=request.user.profile,
            transaction_type=TransactionType.SUBSCRIPTION,
            status=TransactionStatus.PENDING,
            months=months,
            amount_ht=amount_ht,
            tax_amount=tax_amount,
            timbre_fiscal=timbre,
            total_ttc=total
        )
        send_transaction_emails(transaction)
        
        messages.success(request, _("Your payment request has been submitted. Please email proof of payment to commercial@dacnis.tn"))
        return redirect('subscribers:transaction_history')

class TransactionHistoryView(LoginRequiredMixin, View):
    def get(self, request):
        transactions = PaymentTransaction.objects.filter(user=request.user.profile)
        return render(request, 'guard/views/subscribers/transaction_history.html', {'transactions': transactions})

class BoostEventView(LoginRequiredMixin, View):
    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id, client=request.user.profile)
        
        # Check if event starts in > 3 days
        if event.startDate <= timezone.now().date() + timedelta(days=3):
            messages.error(request, _("Cannot boost an event that starts in less than 3 days."))
            return redirect('guard:eventList')
            
        amount_ht = 15.0
        tax_amount = amount_ht * 0.19
        timbre = 1.0
        total = amount_ht + tax_amount + timbre

        transaction = PaymentTransaction.objects.create(
            user=request.user.profile,
            transaction_type=TransactionType.EVENT_BOOST,
            status=TransactionStatus.PENDING,
            event=event,
            amount_ht=amount_ht,
            tax_amount=tax_amount,
            timbre_fiscal=timbre,
            total_ttc=total
        )
        send_transaction_emails(transaction)
        
        messages.success(request, _("Boost request submitted. Please complete the bank transfer."))
        return redirect('subscribers:transaction_history')



# -----------------------------------------------------------------------------
# Staff Views
# -----------------------------------------------------------------------------
class TransactionValidationListView(StaffRequiredMixin, View):
    def get(self, request):
        transactions = PaymentTransaction.objects.filter(status=TransactionStatus.PENDING)
        return render(request, 'guard/views/subscribers/validation_list.html', {'transactions': transactions})

class ValidateTransactionView(StaffRequiredMixin, View):
    def post(self, request, transaction_id):
        transaction = get_object_or_404(PaymentTransaction, id=transaction_id)
        
        if transaction.status == TransactionStatus.PENDING:
            transaction.status = TransactionStatus.VALIDATED
            transaction.validated_at = timezone.now()
            transaction.save()
            
            # Apply logic based on type
            if transaction.transaction_type == TransactionType.SUBSCRIPTION:
                profile = transaction.user
                days_to_add = transaction.months * 30 # roughly
                
                today = timezone.now().date()
                if not profile.subscription_renews_at or profile.subscription_renews_at < today:
                    profile.subscription_renews_at = today + timedelta(days=days_to_add)
                else:
                    profile.subscription_renews_at += timedelta(days=days_to_add)
                profile.subscription_status = 'active'
                profile.save()
                
            elif transaction.transaction_type == TransactionType.EVENT_BOOST:
                if transaction.event:
                    transaction.event.boost = True
                    transaction.event.save()
                    
            elif transaction.transaction_type == TransactionType.AD_BOOST:
                if transaction.ad:
                    transaction.ad.startDate = transaction.ad_start_date
                    transaction.ad.endDate = transaction.ad_end_date
                    transaction.ad.is_active = True
                    transaction.ad.save()
            
            send_validation_email(transaction)
            
            messages.success(request, _("Transaction validated successfully."))
        
        return redirect('subscribers:validation_list')

class CancelTransactionView(StaffRequiredMixin, View):
    def post(self, request, transaction_id):
        transaction = get_object_or_404(PaymentTransaction, id=transaction_id)
        
        if transaction.status == TransactionStatus.PENDING:
            transaction.status = TransactionStatus.CANCELED
            transaction.save()
            
            send_cancellation_email(transaction)
            messages.success(request, _("Transaction canceled and email sent to client."))
        else:
            messages.error(request, _("Transaction cannot be canceled."))
            
        return redirect('subscribers:validation_list')
