from django.db.models import Q
from django.urls import reverse

from .models import Notification


def notification_summary(request):
    user = request.user
    if not user.is_authenticated:
        return {"notification_unread_count": 0, "notification_cursor": 0, "back_url": None}

    membership = user.memberships.filter(
        is_active=True,
        workshop__is_active=True,
    ).select_related("workshop").first()
    if membership is None:
        return {"notification_unread_count": 0, "notification_cursor": 0, "back_url": None}

    visible = Notification.objects.filter(workshop=membership.workshop).filter(
        Q(user=user) | Q(user__isnull=True)
    )
    back_url = None
    route_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
    route_map = {
        "customer_detail": "customer_list",
        "customer_edit": "customer_list",
        "supplier_detail": "supplier_list",
        "supplier_edit": "supplier_list",
        "camper_detail": "fleet:camper_list",
        "camper_edit": "fleet:camper_list",
        "part_detail": "inventory",
        "part_edit": "inventory",
        "part_movement": "inventory",
        "work_order_detail": "orders",
        "bom_edit": "bom_list",
        "bom_create": "bom_list",
        "price_list_edit": "price_lists",
        "price_list_grid": "price_lists",
        "supplier_price_list_detail": "supplier_price_list_list",
        "supplier_price_list_grid": "supplier_price_list_list",
        "purchase_order_detail": "purchase_order_list",
        "purchase_order_receive": "purchase_order_list",
    }
    target_name = route_map.get(route_name)
    if target_name:
        try:
            back_url = reverse(target_name)
        except Exception:
            back_url = None
    return {
        "notification_unread_count": visible.filter(read=False).count(),
        "notification_cursor": visible.order_by("-pk").values_list("pk", flat=True).first() or 0,
        "back_url": back_url,
    }
