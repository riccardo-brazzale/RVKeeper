from django.db import migrations, models


def map_legacy_profiles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(department__in=("technician", "details")).update(profile="mechanic")
    User.objects.filter(department="parts").update(profile="warehouse")
    User.objects.exclude(department__in=("technician", "details", "parts")).update(profile="admin")
    User.objects.filter(is_superuser=True).update(profile="admin")
    User.objects.filter(profile="admin").update(is_staff=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_add_spanish_language")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="profile",
            field=models.CharField(
                choices=[("admin", "Amministratore"), ("warehouse", "Magazziniere"), ("mechanic", "Meccanico")],
                default="mechanic", max_length=20, verbose_name="Profilo",
            ),
        ),
        migrations.RunPython(map_legacy_profiles, migrations.RunPython.noop),
        migrations.RemoveField(model_name="user", name="department"),
        migrations.RemoveField(model_name="user", name="specialty"),
        migrations.RemoveField(model_name="user", name="seniority"),
    ]
