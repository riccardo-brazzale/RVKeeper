from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CustomerItemDiscount, PriceList, PriceListItem


def ensure_workshop_price_list(workshop):
    workshop_list = PriceList.objects.filter(
        workshop=workshop, is_workshop=True,
    ).first()
    if workshop_list is None:
        workshop_list = PriceList.objects.create(
            workshop=workshop,
            code="OFFICINE",
            name="Listino Officine",
            is_workshop=True,
        )
    return workshop_list


def rotate_price_list_prices(price_list):
    if price_list.customer_id:
        raise ValidationError("I listini cliente non hanno rotazione prezzi.")
    with transaction.atomic():
        items = list(
            PriceListItem.objects.select_for_update().filter(price_list=price_list).order_by("pk")
        )
        if not items:
            raise ValidationError("Il listino non contiene articoli da ruotare.")
        rotating_items = [item for item in items if item.future_price is not None]
        for item in rotating_items:
            if item.future_valid_from is None:
                raise ValidationError(
                    f"Imposta la data di validità del prezzo futuro per {item} prima di ruotare."
                )
            item.previous_price = item.unit_price
            item.previous_valid_from = item.valid_from
            item.unit_price = item.future_price
            item.valid_from = item.future_valid_from
            item.future_price = None
            item.future_valid_from = None
            item.save(update_fields=(
                "previous_price", "previous_valid_from", "unit_price", "valid_from",
                "future_price", "future_valid_from",
            ))
    return len(rotating_items), len(items) - len(rotating_items)


def _build_targets(part, labor_article):
    """Return ordered list of target filters from most specific to most generic."""
    if part:
        targets = [{"part": part}]
        if part.article_group_id:
            targets.append({"article_group": part.article_group})
        if part.article_class_id:
            targets.append({"article_class": part.article_class})
    else:
        targets = [{"labor_article": labor_article}]
    return targets


def resolve_item_price(customer, *, part=None, labor_article=None, effective_date=None):
    """Return the applicable list price and customer discount for one catalog item.

    Price lookup cascades: part -> article group -> article class.
    Customer discount lookup follows the same cascade.
    """
    if bool(part) == bool(labor_article):
        raise ValueError("Pass exactly one of part or labor_article")

    effective_date = effective_date or timezone.localdate()
    workshop = part.workshop if part else labor_article.workshop
    targets = _build_targets(part, labor_article)

    default_list = PriceList.objects.filter(workshop=workshop, is_default=True, is_active=True).first()
    workshop_list = PriceList.objects.filter(workshop=workshop, is_workshop=True, is_active=True).first()
    candidates = []
    if customer and customer.price_list_id:
        assigned_list = customer.price_list
        if (
            assigned_list.workshop_id == workshop.pk
            and assigned_list.is_active
        ):
            candidates.append(assigned_list)
    if candidates and candidates[0].customer_id:
        candidates = candidates[:1]
    elif not candidates or not candidates[0].is_default:
        if workshop_list and workshop_list not in candidates:
            candidates.append(workshop_list)
    if default_list and default_list not in candidates:
        candidates.append(default_list)

    list_price = None
    for candidate in candidates:
        for target in targets:
            item = PriceListItem.objects.filter(price_list=candidate, **target).first()
            list_price = item.price_for_date(effective_date) if item else None
            if list_price is not None:
                break
        if list_price is not None:
            break
    discount_percent = Decimal("0.00")
    if customer:
        for target in targets:
            discount = CustomerItemDiscount.objects.filter(customer=customer, **target).values_list(
                "discount_percent", flat=True
            ).first()
            if discount is not None:
                discount_percent = discount
                break

    return {
        "unit_price": list_price,
        "discount_percent": discount_percent,
        "total_unit_price": (
            (list_price * (Decimal("1.00") - discount_percent / Decimal("100"))).quantize(Decimal("0.01"))
            if list_price is not None
            else None
        ),
    }
