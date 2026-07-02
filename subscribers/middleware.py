from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from shared.models import UserProfile

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            
            # Check if user is a client/partner and has a renewal date
            if profile and profile.user_type == UserProfile.UserType.CLIENT_PARTNER and profile.subscription_renews_at:
                today = timezone.now().date()
                
                # If subscription is expired
                if profile.subscription_renews_at < today:
                    # Allow access to payment portal, auth, static, media, and admin
                    allowed_paths = [
                        reverse('subscribers:payment_portal'),
                        reverse('shared:logout'),
                        '/admin/',
                        '/static/',
                        '/media/',
                        '/auth/',
                    ]
                    
                    # If current path is not in allowed paths and doesn't start with them
                    if not any(request.path.startswith(path) for path in allowed_paths):
                        return redirect('subscribers:payment_portal')

        response = self.get_response(request)
        return response
