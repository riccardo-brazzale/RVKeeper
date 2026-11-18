from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("workshops", "0001_initial"),
        ("accounts", "0004_user_profile"),
    ]

    operations = [
        migrations.RemoveField(model_name="membership", name="role"),
        migrations.DeleteModel(name="Role"),
    ]
