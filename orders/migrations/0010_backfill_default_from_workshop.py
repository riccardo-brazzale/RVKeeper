from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


def backfill_default_from_workshop(apps, schema_editor):
    PriceList = apps.get_model("orders", "PriceList")
    PriceListItem = apps.get_model("orders", "PriceListItem")
    database = schema_editor.connection.alias

    for default_list in PriceList.objects.using(database).filter(is_default=True).iterator():
        workshop_list = PriceList.objects.using(database).filter(
            workshop_id=default_list.workshop_id,
            is_workshop=True,
            is_active=True,
        ).first()
        if workshop_list is None:
            continue

        existing_keys = set(
            PriceListItem.objects.using(database).filter(
                price_list_id=default_list.pk,
            ).values_list("part_id", "labor_article_id")
        )
        workshop_items = list(
            PriceListItem.objects.using(database).filter(
                price_list_id=workshop_list.pk,
            )
        )
        for item in workshop_items:
            key = (item.part_id, item.labor_article_id)
            if key in existing_keys:
                continue
            PriceListItem.objects.using(database).create(
                price_list_id=default_list.pk,
                part_id=item.part_id,
                labor_article_id=item.labor_article_id,
                unit_price=(item.unit_price / Decimal("0.80")).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                ),
            )
            existing_keys.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_pricelist_is_workshop_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_default_from_workshop, migrations.RunPython.noop),
    ]
