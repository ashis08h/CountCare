
from django.urls import path

from .views import (EmailMarketingCustomerListAPIView,
                    EmailCampaignListCreateAPIView,
                    EmailCampaignDetailAPIView,
                    EmailCampaignPauseAPIView,
                    EmailCampaignActivateAPIView
                    )


urlpatterns = [
    path(
        "customers/",
        EmailMarketingCustomerListAPIView.as_view(),
        name="email-marketing-customers",
    ),

    path(
            "campaigns/",
            EmailCampaignListCreateAPIView.as_view(),
            name="email-marketing-campaigns",
        ),

    path(
        "campaigns/<int:pk>/",
        EmailCampaignDetailAPIView.as_view(),
        name="email-marketing-campaign-detail",
    ),

    path(
        "campaigns/<int:pk>/pause/",
        EmailCampaignPauseAPIView.as_view(),
        name="email-marketing-campaign-pause",
    ),

    path(
        "campaigns/<int:pk>/activate/",
        EmailCampaignActivateAPIView.as_view(),
        name="email-marketing-campaign-activate",
    ),
]
