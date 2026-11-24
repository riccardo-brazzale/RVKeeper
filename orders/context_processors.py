from django.db.models import Q

from .models import Notification


def notification_summary(request):
    user = request.user
    if not user.is_authenticated:
        return {"notification_unread_count": 0, "notification_cursor": 0}

    membership = user.memberships.filter(
        is_active=True,
        workshop__is_active=True,
    ).select_related("workshop").first()
    if membership is None:
        return {"notification_unread_count": 0, "notification_cursor": 0}

    visible = Notification.objects.filter(workshop=membership.workshop).filter(
        Q(user=user) | Q(user__isnull=True)
    )
    return {
        "notification_unread_count": visible.filter(read=False).count(),
        "notification_cursor": visible.order_by("-pk").values_list("pk", flat=True).first() or 0,
    }
