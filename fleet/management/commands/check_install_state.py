from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Rifiuta bootstrap su un database con schema incompatibile o migrazioni iniziali pendenti."

    def handle(self, *args, **options):
        tables = set(connection.introspection.table_names())
        app_tables = {model._meta.db_table for model in apps.get_models()}
        existing_app_tables = tables & app_tables

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        pending_initial = [
            f"{migration.app_label}.{migration.name}"
            for migration, _ in plan
            if migration.initial
        ]
        if existing_app_tables and pending_initial:
            sample = ", ".join(sorted(existing_app_tables)[:8])
            pending = ", ".join(pending_initial)
            raise CommandError(
                "Database già popolato ma con migrazioni iniziali pendenti. "
                f"Tabelle esistenti: {sample}. Migrazioni: {pending}. "
                "Bootstrap interrotto senza modificare lo schema."
            )

        if not plan:
            missing_tables = sorted(
                {
                    model._meta.db_table
                    for model in apps.get_models()
                    if model._meta.managed
                    and not model._meta.proxy
                    and model._meta.db_table not in tables
                }
            )
            if missing_tables:
                raise CommandError(
                    "Le migrazioni risultano applicate ma mancano tabelle applicative: "
                    f"{', '.join(missing_tables[:12])}. Bootstrap interrotto."
                )

        missing_columns = []
        with connection.cursor() as cursor:
            for model in apps.get_models():
                table = model._meta.db_table
                if table not in existing_app_tables:
                    continue
                actual_columns = {
                    column.name
                    for column in connection.introspection.get_table_description(cursor, table)
                }
                for field in model._meta.local_fields:
                    if field.column and field.column not in actual_columns:
                        missing_columns.append(f"{table}.{field.column}")

        if missing_columns:
            sample = ", ".join(missing_columns[:12])
            raise CommandError(
                "Lo schema reale non corrisponde ai modelli Django. "
                f"Colonne mancanti: {sample}. Bootstrap interrotto senza modificare lo schema."
            )

        self.stdout.write(self.style.SUCCESS("Database vuoto o schema coerente con i modelli."))
