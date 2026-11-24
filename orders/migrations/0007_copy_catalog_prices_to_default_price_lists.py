from django.db import migrations


def copy_catalog_prices(apps, schema_editor):
    Part = apps.get_model("parts", "Part")
    LaborArticle = apps.get_model("orders", "LaborArticle")
    PriceList = apps.get_model("orders", "PriceList")
    PriceListItem = apps.get_model("orders", "PriceListItem")
    database = schema_editor.connection.alias

    workshop_ids = set(
        Part.objects.using(database).values_list("workshop_id", flat=True).distinct()
    )
    workshop_ids.update(
        LaborArticle.objects.using(database).values_list("workshop_id", flat=True).distinct()
    )

    for workshop_id in sorted(workshop_ids):
        price_list = PriceList.objects.using(database).filter(
            workshop_id=workshop_id,
            is_default=True,
        ).first()
        if price_list is None:
            code = "DEFAULT"
            suffix = 1
            while PriceList.objects.using(database).filter(
                workshop_id=workshop_id,
                code=code,
            ).exists():
                code = f"DEFAULT-{suffix}"
                suffix += 1
            price_list = PriceList.objects.using(database).create(
                workshop_id=workshop_id,
                code=code,
                name="Listino generale",
                is_default=True,
                is_active=True,
            )

        existing_part_ids = set(
            PriceListItem.objects.using(database).filter(
                price_list_id=price_list.pk,
                part__isnull=False,
            ).values_list("part_id", flat=True)
        )
        PriceListItem.objects.using(database).bulk_create(
            [
                PriceListItem(
                    price_list_id=price_list.pk,
                    part_id=part_id,
                    unit_price=price,
                )
                for part_id, price in Part.objects.using(database).filter(
                    workshop_id=workshop_id,
                ).values_list("pk", "sale_price")
                if part_id not in existing_part_ids
            ],
            batch_size=500,
        )

        existing_labor_article_ids = set(
            PriceListItem.objects.using(database).filter(
                price_list_id=price_list.pk,
                labor_article__isnull=False,
            ).values_list("labor_article_id", flat=True)
        )
        PriceListItem.objects.using(database).bulk_create(
            [
                PriceListItem(
                    price_list_id=price_list.pk,
                    labor_article_id=article_id,
                    unit_price=rate,
                )
                for article_id, rate in LaborArticle.objects.using(database).filter(
                    workshop_id=workshop_id,
                ).values_list("pk", "hourly_rate")
                if article_id not in existing_labor_article_ids
            ],
            batch_size=500,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_pricelist_pricelistitem_customeritemdiscount_and_more"),
        ("parts", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(copy_catalog_prices, migrations.RunPython.noop),
    ]
