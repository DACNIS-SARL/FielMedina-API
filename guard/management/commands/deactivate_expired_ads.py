from django.core.management.base import BaseCommand
from django.utils import timezone
from guard.models import Ad

class Command(BaseCommand):
    help = 'Deactivate ads that have expired (endDate < today)'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        expired_ads = Ad.objects.filter(is_active=True, endDate__lt=today)
        count = expired_ads.count()
        
        if count > 0:
            expired_ads.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'Successfully deactivated {count} expired ad(s).'))
        else:
            self.stdout.write(self.style.SUCCESS('No expired ads found to deactivate.'))
