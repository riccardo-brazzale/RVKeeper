import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0002_initial")]

    operations = [
        migrations.CreateModel(
            name="LaborArticle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40)),
                ("description", models.CharField(max_length=200)),
                ("standard_rate", models.DecimalField(decimal_places=2, default=65, max_digits=9, verbose_name="Tariffa oraria standard")),
                ("holiday_rate", models.DecimalField(decimal_places=2, default=95, max_digits=9, verbose_name="Tariffa oraria festiva")),
                ("discounted_rate", models.DecimalField(decimal_places=2, default=50, max_digits=9, verbose_name="Tariffa oraria scontata")),
                ("is_active", models.BooleanField(default=True, verbose_name="Attivo")),
                ("workshop", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="labor_articles", to="workshops.workshop")),
            ],
            options={"verbose_name": "Articolo manodopera", "verbose_name_plural": "Articoli manodopera", "ordering": ("code",)},
        ),
        migrations.AddField(
            model_name="workorder", name="tariff_type",
            field=models.CharField(choices=[("standard", "Standard"), ("holiday", "Festiva"), ("discounted", "Scontata")], default="standard", max_length=20, verbose_name="Tipologia tariffa"),
        ),
        migrations.AddField(
            model_name="job", name="labor_article",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="jobs", to="orders.laborarticle", verbose_name="Articolo manodopera"),
        ),
        migrations.AddConstraint(
            model_name="laborarticle",
            constraint=models.UniqueConstraint(fields=("workshop", "code"), name="unique_labor_article_per_workshop"),
        ),
    ]
