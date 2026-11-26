
from django.urls import path

from .views import EmailMarketingCustomerListAPIView


urlpatterns = [
    path(
        "customers/",
        EmailMarketingCustomerListAPIView.as_view(),
        name="email-marketing-customers",
    ),
]
