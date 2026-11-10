from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshops", "0001_initial"),
    ]

    operations = [
        migrations.AlterConstraint(
            model_name="membership",
            name="unique_user_per_workshop",
            constraint=models.UniqueConstraint(
                fields=("user", "workshop"),
                name="unique_user_per_workshop",
                violation_error_message=(
                    "Questo utente ha già un'appartenenza per questa officina. "
                    "Modifica quella esistente per cambiare ruolo."
                ),
            ),
        ),
    ]
