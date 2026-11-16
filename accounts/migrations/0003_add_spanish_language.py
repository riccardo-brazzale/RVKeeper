from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_limit_preferred_language_choices"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="preferred_language",
            field=models.CharField(
                choices=[("en-us", "English"), ("it", "Italiano"), ("es", "Español")],
                default="en-us",
                max_length=10,
                verbose_name="Lingua preferita",
            ),
        ),
    ]
