from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from shared.models import UserProfile
from guard.models import Event, Ad
from datetime import timedelta

class Command(BaseCommand):
    help = 'Runs daily checks for subscription expirations and boosted items.'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        self.stdout.write(self.style.SUCCESS(f"Running daily checks for {today}..."))

        # 1. Process Event Boosts
        # Disable boosts for events that start today or earlier
        events_updated = Event.objects.filter(boost=True, startDate__lte=today).update(boost=False)
        self.stdout.write(self.style.SUCCESS(f"Disabled boost for {events_updated} expired events."))

        # 2. Process Ad Boosts
        # Disable ads where endDate < today
        ads_updated = Ad.objects.filter(is_active=True, endDate__lt=today).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f"Disabled {ads_updated} expired ads."))

        # 3. Process Subscription Expirations and Emails
        clients = UserProfile.objects.filter(
            user_type=UserProfile.UserType.CLIENT_PARTNER,
            subscription_renews_at__isnull=False
        )

        emails_sent = 0
        for client in clients:
            days_left = (client.subscription_renews_at - today).days

            if days_left in [15, 7, 3, 0]:
                self.send_expiration_email(client, days_left)
                emails_sent += 1
            elif days_left < 0 and client.subscription_status != 'expired':
                client.subscription_status = 'expired'
                client.save()

        self.stdout.write(self.style.SUCCESS(f"Sent {emails_sent} expiration warning emails."))
        self.stdout.write(self.style.SUCCESS("Daily checks completed successfully."))

    def send_expiration_email(self, profile, days_left):
        if not profile.user.email:
            return

        subject = "FielMedina - Action Required: Subscription Renewal"
        if days_left > 0:
            message = f"Hello {profile.user.get_full_name() or profile.user.username},\n\nYour subscription to FielMedina is expiring in {days_left} days.\nTo maintain access to your dashboard, please log in and complete your payment via bank transfer.\n\nThank you,\nThe FielMedina Team"
        else:
            message = f"Hello {profile.user.get_full_name() or profile.user.username},\n\nYour subscription to FielMedina has expired today.\nYour dashboard access is now restricted. Please log in and submit a payment to restore your access.\n\nThank you,\nThe FielMedina Team"

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [profile.user.email],
                fail_silently=True,
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to send email to {profile.user.email}: {e}"))
