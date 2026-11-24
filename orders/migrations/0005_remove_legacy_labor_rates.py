from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_split_labor_articles"),
    ]

    operations = [
        migrations.RemoveField(model_name="laborarticle", name="discounted_rate"),
        migrations.RemoveField(model_name="laborarticle", name="holiday_rate"),
        migrations.RemoveField(model_name="laborarticle", name="standard_rate"),
        migrations.RemoveField(model_name="workorder", name="tariff_type"),
    ]
