
class CompanyScopedQuerySetMixin:
    """
    Restricts model querysets to the logged-in user's company.

    Use this mixin on DRF views that have a queryset.
    """

    company_field = "company"

    def get_queryset(self):

        queryset = super().get_queryset()

        membership = getattr(
            self.request,
            "company_membership",
            None,
        )

        if not membership:
            return queryset.none()

        return queryset.filter(
            **{
                self.company_field: membership.company
            }
        )
