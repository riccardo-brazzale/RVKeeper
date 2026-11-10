import re

from django.db import migrations, models


def populate_usernames(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    database = schema_editor.connection.alias
    used_usernames = set()

    for user in User.objects.using(database).only("pk", "email").iterator():
        base = (user.email or "").split("@", 1)[0].strip().lower()
        base = re.sub(r"[^a-z0-9.@+_-]", "_", base)[:150] or "utente"
        username = base
        suffix = 2
        while username.lower() in used_usernames:
            ending = str(suffix)
            username = f"{base[:150 - len(ending)]}{ending}"
            suffix += 1

        used_usernames.add(username.lower())
        User.objects.using(database).filter(pk=user.pk).update(username=username)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_department_user_specialty_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(
                max_length=150,
                null=True,
                blank=True,
                unique=True,
                verbose_name="Nome utente",
            ),
        ),
        migrations.RunPython(populate_usernames, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                max_length=150,
                unique=True,
                verbose_name="Nome utente",
            ),
        ),
    ]
