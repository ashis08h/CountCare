
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import CashCountPermission
from customers.models import Customer
from customers.permissions import ToggleAPIPermission

from .serializers import EmailCampaignCustomerSerializer, EmailCampaignSerializer

from .models import EmailCampaign

from django.utils import timezone
from rest_framework import status
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from .services.scheduling import calculate_next_run_at


class EmailMarketingPermissionMixin:

    permission_classes = [
        IsAuthenticated,
        ToggleAPIPermission,
        CashCountPermission,
    ]

    permission_map = {
        "GET": "email_marketing_view",
        "POST": "email_marketing_add",
        "PUT": "email_marketing_change",
        "PATCH": "email_marketing_change",
        "DELETE": "email_marketing_delete",
    }

    def get_permissions(self):

        self.required_permission = self.permission_map.get(
            self.request.method
        )

        return super().get_permissions()

    def get_company(self):
        return self.request.company_membership.company


class EmailMarketingCustomerListAPIView(
    EmailMarketingPermissionMixin,
    ListAPIView,
):

    serializer_class = EmailCampaignCustomerSerializer

    def get_queryset(self):

        company = self.get_company()

        queryset = Customer.objects.filter(
            company=company,
            status="ACTIVE",
        ).exclude(
            email__isnull=True,
        ).exclude(
            email__exact="",
        )

        search = self.request.query_params.get(
            "search",
            "",
        ).strip()

        if search:

            from django.db.models import Q

            queryset = queryset.filter(
                Q(business_name__icontains=search)
                | Q(contact_person__icontains=search)
                | Q(email__icontains=search)
                | Q(customer_code__icontains=search)
            )

        return queryset.order_by(
            "business_name",
            "contact_person",
        )



class EmailCampaignListCreateAPIView(
    EmailMarketingPermissionMixin,
    ListCreateAPIView,
):

    serializer_class = EmailCampaignSerializer

    permission_map = {
        "GET": "email_marketing_view",
        "POST": "email_marketing_add",
    }

    def get_queryset(self):

        return (
            EmailCampaign.objects
            .filter(
                company=self.get_company(),
            )
            .exclude(
                status=EmailCampaign.Status.DELETED,
            )
            .prefetch_related("recipients")
            .order_by("-created_at")
        )

    def get_serializer_context(self):

        context = super().get_serializer_context()
        context["company"] = self.get_company()

        return context


class EmailCampaignDetailAPIView(
    EmailMarketingPermissionMixin,
    RetrieveUpdateDestroyAPIView,
):
    serializer_class = EmailCampaignSerializer

    permission_map = {
        "GET": "email_marketing_view",
        "PUT": "email_marketing_change",
        "PATCH": "email_marketing_change",
        "DELETE": "email_marketing_delete",
    }

    def get_queryset(self):
        return (
            EmailCampaign.objects
            .filter(company=self.get_company())
            .exclude(status=EmailCampaign.Status.DELETED)
            .prefetch_related("recipients")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["company"] = self.get_company()
        return context

    def update(self, request, *args, **kwargs):
        campaign = self.get_object()

        if campaign.status not in [
            EmailCampaign.Status.DRAFT,
            EmailCampaign.Status.PAUSED,
        ]:
            return Response(
                {
                    "detail": (
                        "Only draft or paused campaigns can be edited."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        campaign = self.get_object()

        campaign.status = EmailCampaign.Status.DELETED
        campaign.is_active = False
        campaign.next_run_at = None
        campaign.deleted_at = timezone.now()
        campaign.updated_by = request.user

        campaign.save(
            update_fields=[
                "status",
                "is_active",
                "next_run_at",
                "deleted_at",
                "updated_by",
                "updated_at",
            ]
        )

        return Response(
            {"detail": "Campaign deleted successfully."},
            status=status.HTTP_200_OK,
        )


class EmailCampaignPauseAPIView(
    EmailMarketingPermissionMixin,
    APIView,
):
    permission_map = {
        "POST": "email_marketing_change",
    }

    def post(self, request, pk):
        campaign = EmailCampaign.objects.filter(
            id=pk,
            company=self.get_company(),
        ).exclude(
            status=EmailCampaign.Status.DELETED
        ).first()

        if not campaign:
            return Response(
                {"detail": "Campaign not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if campaign.status != EmailCampaign.Status.ACTIVE:
            return Response(
                {
                    "detail": (
                        "Only active campaigns can be paused."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign.status = EmailCampaign.Status.PAUSED
        campaign.is_active = False
        campaign.next_run_at = None
        campaign.updated_by = request.user

        campaign.save(
            update_fields=[
                "status",
                "is_active",
                "next_run_at",
                "updated_by",
                "updated_at",
            ]
        )

        return Response({
            "detail": "Campaign paused successfully.",
            "campaign_id": campaign.id,
            "status": campaign.status,
        })


class EmailCampaignActivateAPIView(
    EmailMarketingPermissionMixin,
    APIView,
):
    permission_map = {
        "POST": "email_marketing_approve",
    }

    @transaction.atomic
    def post(self, request, pk):
        campaign = (
            EmailCampaign.objects
            .select_for_update()
            .filter(
                id=pk,
                company=self.get_company(),
            )
            .exclude(status=EmailCampaign.Status.DELETED)
            .first()
        )

        if not campaign:
            return Response(
                {"detail": "Campaign not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if campaign.status not in [
            EmailCampaign.Status.DRAFT,
            EmailCampaign.Status.PAUSED,
        ]:
            return Response(
                {
                    "detail": (
                        "Only draft or paused campaigns can be activated."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not campaign.recipients.exists():
            return Response(
                {
                    "detail": (
                        "Add at least one recipient before activating "
                        "the campaign."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not campaign.subject.strip() or not campaign.message.strip():
            return Response(
                {"detail": "Campaign subject and message are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            next_run_at = calculate_next_run_at(campaign)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if next_run_at is None:
            return Response(
                {
                    "detail": (
                        "No future execution is available for this "
                        "campaign schedule. Check the scheduled date, "
                        "start date and end date."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign.status = EmailCampaign.Status.ACTIVE
        campaign.is_active = True
        campaign.next_run_at = next_run_at
        campaign.updated_by = request.user

        campaign.save(
            update_fields=[
                "status",
                "is_active",
                "next_run_at",
                "updated_by",
                "updated_at",
            ]
        )

        return Response(
            {
                "detail": "Campaign activated successfully.",
                "campaign_id": campaign.id,
                "status": campaign.status,
                "next_run_at": campaign.next_run_at,
                "timezone": campaign.timezone,
            },
            status=status.HTTP_200_OK,
        )