from django.urls import path
from . import views

app_name = 'subscribers'

urlpatterns = [
    path('payment-portal/', views.PaymentPortalView.as_view(), name='payment_portal'),
    path('transaction-history/', views.TransactionHistoryView.as_view(), name='transaction_history'),
    path('boost/event/<int:event_id>/', views.BoostEventView.as_view(), name='boost_event'),

    
    # Staff / Admin endpoints
    path('validation-list/', views.TransactionValidationListView.as_view(), name='validation_list'),
    path('validate/<int:transaction_id>/', views.ValidateTransactionView.as_view(), name='validate_transaction'),
    path('cancel/<int:transaction_id>/', views.CancelTransactionView.as_view(), name='cancel_transaction'),
]
