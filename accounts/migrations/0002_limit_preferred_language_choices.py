from django.db import migrations, models


def normalize_existing_languages(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.exclude(preferred_language__in=("en-us", "it")).update(
        preferred_language="en-us"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_existing_languages, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="preferred_language",
            field=models.CharField(
                choices=[("en-us", "English"), ("it", "Italiano")],
                default="en-us",
                max_length=10,
                verbose_name="Lingua preferita",
            ),
        ),
    ]
