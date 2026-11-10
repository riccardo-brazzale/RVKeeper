from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_user_email_not_unique"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={"verbose_name": "Utente", "verbose_name_plural": "Utenti"},
        ),
    ]
