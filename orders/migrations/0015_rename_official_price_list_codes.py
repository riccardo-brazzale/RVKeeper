from django.db import migrations


def rename_official_price_lists(apps, schema_editor):
    PriceList = apps.get_model("orders", "PriceList")
    for price_list in PriceList.objects.filter(is_default=True).iterator():
        price_list.code = "CLIENTE"
        price_list.name = "Listino Cliente"
        price_list.save(update_fields=("code", "name"))
    for price_list in PriceList.objects.filter(is_workshop=True).iterator():
        price_list.code = "OFFICINE"
        price_list.name = "Listino Officine"
        price_list.save(update_fields=("code", "name"))


def restore_official_price_list_codes(apps, schema_editor):
    PriceList = apps.get_model("orders", "PriceList")
    for price_list in PriceList.objects.filter(is_default=True).iterator():
        price_list.code = "DEFAULT"
        price_list.name = "Listino Principale"
        price_list.save(update_fields=("code", "name"))
    for price_list in PriceList.objects.filter(is_workshop=True).iterator():
        price_list.code = "OFFICINA"
        price_list.name = "Listino Officina"
        price_list.save(update_fields=("code", "name"))


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0014_job_invoice_hourly_rate_override_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_official_price_lists, restore_official_price_list_codes),
    ]
