from django.db import migrations


def create_catalogs(apps, schema_editor):
    Category = apps.get_model("fleet", "DocumentCategory")
    for order, (code, name) in enumerate([
        ("foto-esterni", "Foto esterni"),
        ("foto-interni", "Foto interni"),
        ("motore", "Motore"),
        ("accessori", "Accessori"),
        ("libretto", "Libretto e documenti veicolo"),
        ("manuale", "Manuale / scheda tecnica"),
        ("manutenzione", "Manutenzione e riparazioni"),
        ("garanzia", "Garanzia"),
        ("acquisto", "Acquisto / fattura"),
        ("altro", "Altro"),
    ]):
        Category.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order})

    PauseReason = apps.get_model("orders", "PauseReason")
    for order, (code, label) in enumerate([
        ("caffe", "Pausa caffè"),
        ("bagno", "Pausa bagno"),
        ("sigaretta", "Pausa sigaretta"),
        ("pranzo", "Pausa pranzo"),
        ("altra", "Altra pausa"),
    ]):
        PauseReason.objects.get_or_create(code=code, defaults={"label": label, "sort_order": order})


class Migration(migrations.Migration):
    dependencies = [
        ("fleet", "0003_initial"),
        ("orders", "0002_initial"),
    ]

    operations = [migrations.RunPython(create_catalogs, migrations.RunPython.noop)]
