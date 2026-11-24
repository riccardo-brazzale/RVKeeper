from django.db import migrations


def rename_default_price_list(apps, schema_editor):
    PriceList = apps.get_model("orders", "PriceList")
    PriceList.objects.filter(is_default=True, name="Listino Default").update(name="Listino Principale")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_customeritemdiscount_article_class_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_default_price_list, migrations.RunPython.noop),
    ]