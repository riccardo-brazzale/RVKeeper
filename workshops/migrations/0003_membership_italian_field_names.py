from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workshops", "0002_membership_constraint_message"),
    ]

    operations = [
        migrations.AlterField(
            model_name="membership",
            name="user",
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name="memberships",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Utente",
            ),
        ),
        migrations.AlterField(
            model_name="membership",
            name="workshop",
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name="memberships",
                to="workshops.workshop",
                verbose_name="Officina",
            ),
        ),
        migrations.AlterField(
            model_name="membership",
            name="role",
            field=models.ForeignKey(
                on_delete=models.PROTECT,
                related_name="memberships",
                to="workshops.role",
                verbose_name="Ruolo",
            ),
        ),
        migrations.AlterField(
            model_name="membership",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="Attiva"),
        ),
    ]
