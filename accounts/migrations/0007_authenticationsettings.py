from django.db import migrations, models


def create_default_authentication_settings(apps, schema_editor):
    AuthenticationSettings = apps.get_model("accounts", "AuthenticationSettings")
    AuthenticationSettings.objects.get_or_create(
        pk=1,
        defaults={
            "idle_timeout_minutes": 15,
            "session_duration_hours": 10,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_alter_user_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthenticationSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idle_timeout_minutes", models.PositiveIntegerField(default=15, verbose_name="Inattivita consentita (minuti)")),
                ("session_duration_hours", models.PositiveIntegerField(default=10, verbose_name="Durata massima sessione (ore)")),
            ],
            options={
                "verbose_name": "Impostazioni di autenticazione",
                "verbose_name_plural": "Impostazioni di autenticazione",
            },
        ),
        migrations.RunPython(
            create_default_authentication_settings,
            migrations.RunPython.noop,
        ),
    ]
