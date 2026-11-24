import django.db.models.deletion
from django.db import migrations, models


MODEL_MOVES = (
    ("DocumentCategory", "orders"),
    ("WarrantyClaim", "orders"),
    ("WarrantyReturn", "orders"),
    ("JobNote", "orders"),
    ("Attachment", "orders"),
    ("Notification", "orders"),
    ("TimeEvent", "orders"),
    ("JobAssignment", "orders"),
    ("AuditLog", "orders"),
    ("JobParticipation", "orders"),
    ("PartsRequest", "parts"),
    ("JobPartUsage", "parts"),
    ("WarehouseNote", "parts"),
    ("WarehouseNoteRead", "parts"),
)


def move_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model_name, target_app in MODEL_MOVES:
        model = model_name.lower()
        old_type = ContentType.objects.filter(app_label="fleet", model=model).first()
        if old_type is None:
            continue
        if ContentType.objects.filter(app_label=target_app, model=model).exists():
            raise RuntimeError(
                f"Content type {target_app}.{model} already exists; refusing to merge permissions."
            )
        old_type.app_label = target_app
        old_type.save(update_fields=("app_label",))


def restore_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model_name, source_app in reversed(MODEL_MOVES):
        model = model_name.lower()
        moved_type = ContentType.objects.filter(app_label=source_app, model=model).first()
        if moved_type is None:
            continue
        if ContentType.objects.filter(app_label="fleet", model=model).exists():
            raise RuntimeError(
                f"Content type fleet.{model} already exists; refusing to merge permissions."
            )
        moved_type.app_label = "fleet"
        moved_type.save(update_fields=("app_label",))


class Migration(migrations.Migration):

    dependencies = [
        ("clientandsuppliers", "0006_alter_contactdocument_category"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("fleet", "0009_warehousenote_warehousenoteread_and_more"),
        ("orders", "0018_warrantyreturn_parts_request_and_more"),
        ("parts", "0009_alter_partdocument_category_partsrequest_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="camperphoto",
                    name="category",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="camper_photos",
                        to="orders.documentcategory",
                    ),
                ),
                migrations.DeleteModel(name="Attachment"),
                migrations.DeleteModel(name="AuditLog"),
                migrations.DeleteModel(name="JobAssignment"),
                migrations.DeleteModel(name="JobNote"),
                migrations.DeleteModel(name="JobParticipation"),
                migrations.DeleteModel(name="Notification"),
                migrations.DeleteModel(name="TimeEvent"),
                migrations.DeleteModel(name="WarehouseNoteRead"),
                migrations.DeleteModel(name="WarehouseNote"),
                migrations.DeleteModel(name="WarrantyReturn"),
                migrations.DeleteModel(name="PartsRequest"),
                migrations.DeleteModel(name="JobPartUsage"),
                migrations.DeleteModel(name="WarrantyClaim"),
                migrations.DeleteModel(name="DocumentCategory"),
            ],
        ),
        migrations.RunPython(move_content_types, restore_content_types),
    ]
