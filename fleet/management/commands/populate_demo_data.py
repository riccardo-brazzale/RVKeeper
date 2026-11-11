from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clientandsuppliers.models import CamperOwner
from fleet.models import Camper
from parts.models import Part, PartSupplierOffer
from workshops.models import Workshop


CONTACTS = [
    {
        "kind": "customer", "first_name": "Emily", "last_name": "Carter",
        "phone": "+1-206-555-0101", "email": "emily.carter@contacts.example",
        "address": "120 Pine Street, Seattle, WA", "postal_code": "98101", "city": "Seattle",
    },
    {
        "kind": "customer", "first_name": "Michael", "last_name": "Turner",
        "phone": "+1-541-555-0102", "email": "michael.turner@contacts.example",
        "address": "45 Wall Street, Bend, OR", "postal_code": "97701", "city": "Bend",
    },
    {
        "kind": "customer", "first_name": "Sarah", "last_name": "Mitchell",
        "phone": "+1-512-555-0103", "email": "sarah.mitchell@contacts.example",
        "address": "830 Congress Avenue, Austin, TX", "postal_code": "78701", "city": "Austin",
    },
    {
        "kind": "customer", "first_name": "David", "last_name": "Brooks",
        "phone": "+1-303-555-0104", "email": "david.brooks@contacts.example",
        "address": "72 Blake Street, Denver, CO", "postal_code": "80202", "city": "Denver",
    },
    {
        "kind": "customer", "first_name": "Olivia", "last_name": "Parker",
        "phone": "+1-813-555-0105", "email": "olivia.parker@contacts.example",
        "address": "19 Bayshore Boulevard, Tampa, FL", "postal_code": "33606", "city": "Tampa",
    },
    {
        "kind": "customer", "first_name": "Noah", "last_name": "Bennett",
        "phone": "+1-207-555-0106", "email": "noah.bennett@contacts.example",
        "address": "56 Fore Street, Portland, ME", "postal_code": "04101", "city": "Portland",
    },
    {
        "kind": "customer", "first_name": "Grace", "last_name": "Foster",
        "phone": "+1-602-555-0107", "email": "grace.foster@contacts.example",
        "address": "210 Central Avenue, Phoenix, AZ", "postal_code": "85004", "city": "Phoenix",
    },
    {
        "kind": "both", "is_company": True, "company_name": "Cascade RV Outfitters LLC",
        "phone": "+1-503-555-0108", "email": "office@cascade-rv.example",
        "address": "340 Harbor Way, Portland, OR", "postal_code": "97205", "city": "Portland",
    },
    {
        "kind": "supplier", "is_company": True, "company_name": "Summit Camper Components Inc",
        "phone": "+1-720-555-0109", "email": "sales@summit-components.example",
        "address": "88 Union Boulevard, Lakewood, CO", "postal_code": "80228", "city": "Lakewood",
    },
    {
        "kind": "supplier", "is_company": True, "company_name": "Pacific Trail Parts LLC",
        "phone": "+1-619-555-0110", "email": "orders@pacific-trail.example",
        "address": "640 Harbor Drive, San Diego, CA", "postal_code": "92101", "city": "San Diego",
    },
    {
        "kind": "supplier", "is_company": True, "company_name": "Northstar RV Supply Co",
        "phone": "+1-612-555-0111", "email": "info@northstar-rv.example",
        "address": "15 Washington Avenue, Minneapolis, MN", "postal_code": "55401", "city": "Minneapolis",
    },
    {
        "kind": "both", "first_name": "Avery", "last_name": "Coleman",
        "phone": "+1-406-555-0112", "email": "avery.coleman@contacts.example",
        "address": "205 Main Street, Bozeman, MT", "postal_code": "59715", "city": "Bozeman",
    },
]

PARTS = [
    ("DEMO-PART-001", "Engine oil filter", "Spin-on oil filter for sample motorhome service", "each", "8.50", "15.00", 20, 5, "A-01"),
    ("DEMO-PART-002", "Engine air filter", "Replacement air filter, medium chassis", "each", "18.00", "32.00", 25, 6, "A-02"),
    ("DEMO-PART-003", "Diesel fuel filter", "Water-separating diesel filter cartridge", "each", "24.00", "42.00", 18, 4, "A-03"),
    ("DEMO-PART-004", "Serpentine belt", "Accessory drive belt for demo engine platform", "each", "29.00", "49.00", 8, 2, "A-04"),
    ("DEMO-PART-005", "12V water pump", "Fresh water diaphragm pump, 3.0 GPM", "each", "76.00", "119.00", 5, 2, "B-01"),
    ("DEMO-PART-006", "Fresh water filter", "Inline sediment filter cartridge", "each", "12.00", "21.00", 14, 4, "B-02"),
    ("DEMO-PART-007", "House battery 100Ah", "12V deep-cycle lithium house battery", "each", "385.00", "529.00", 3, 1, "B-03"),
    ("DEMO-PART-008", "Roof air conditioner", "Low-profile 13.5k BTU rooftop cooling unit", "each", "895.00", "1249.00", 2, 1, "C-01"),
    ("DEMO-PART-009", "Awning drive motor", "12V replacement motor for powered awning", "each", "142.00", "219.00", 4, 1, "C-02"),
    ("DEMO-PART-010", "Brake pad kit", "Front axle brake pad set, demonstration stock", "set", "58.00", "94.00", 7, 2, "C-03"),
    ("DEMO-PART-011", "RV roof sealant", "Self-leveling sealant, 10 oz tube", "tube", "8.00", "14.00", 30, 10, "D-01"),
    ("DEMO-PART-012", "LED marker light", "Amber 12V exterior clearance lamp", "each", "6.50", "12.00", 16, 5, "D-02"),
]

CAMPER_MODELS = [
    "Trailwind 21", "Mesa Touring 24", "Redwood Class C 26", "High Desert 28",
    "Blue Lake 22", "Canyon Explorer 25", "Pine Ridge 30", "Silver Pass 23",
    "Sagebrush 27", "Cascade Cruiser 29", "Juniper 24", "Summit Voyager 31",
]
REGISTRATION_YEARS = [2017, 2019, 2021, 2018, 2022, 2016, 2023, 2020, 2015, 2024, 2019, 2022]


class Command(BaseCommand):
    help = "Popola un'officina USA con contatti, ricambi, offerte e camper fittizi, senza duplicare i record."

    def add_arguments(self, parser):
        parser.add_argument(
            "--workshop",
            help="Slug dell'officina USA da popolare. Se omesso, deve essercene una sola attiva.",
        )

    def handle(self, *args, **options):
        workshops = Workshop.objects.filter(is_active=True, country="US")
        if options["workshop"]:
            workshops = workshops.filter(slug=options["workshop"])
        else:
            count = workshops.count()
            if count != 1:
                names = ", ".join(f"{item.name} ({item.slug})" for item in workshops)
                raise CommandError(
                    f"Trovate {count} officine USA attive. Specificare --workshop SLUG. {names}"
                )

        workshop = workshops.first()
        if workshop is None:
            raise CommandError("Officina attiva non trovata. Lo slug deve indicare un'officina con country=US.")

        counts = {"contacts": 0, "parts": 0, "offers": 0, "campers": 0}
        with transaction.atomic():
            for row in CONTACTS:
                data = dict(row)
                is_company = data.pop("is_company", False)
                defaults = {
                    **data,
                    "is_company": is_company,
                    "country": "US",
                    "notes": "Fictional sample record generated for testing.",
                }
                contact, created = CamperOwner.objects.get_or_create(
                    workshop=workshop,
                    email=row["email"],
                    defaults=defaults,
                )
                contact.full_clean()
                counts["contacts"] += int(created)

            suppliers = list(
                CamperOwner.objects.filter(workshop=workshop, kind__in=("supplier", "both")).order_by("email")
            )
            customers = list(
                CamperOwner.objects.filter(workshop=workshop, kind__in=("customer", "both")).order_by("email")
            )
            if not suppliers or not customers:
                raise CommandError("Impossibile creare offerte o camper: servono clienti e fornitori nell'officina.")

            parts = []
            for index, row in enumerate(PARTS, start=1):
                number, name, description, unit, cost, sale, quantity, min_stock, location = row
                part, created = Part.objects.get_or_create(
                    workshop=workshop,
                    part_number=number,
                    defaults={
                        "name": name,
                        "description": description,
                        "unit": unit,
                        "cost_price": cost,
                        "sale_price": sale,
                        "standard_minutes": 20,
                        "quantity": quantity,
                        "min_stock": min_stock,
                        "location": location,
                    },
                )
                part.full_clean()
                counts["parts"] += int(created)
                parts.append(part)

                supplier = suppliers[index % len(suppliers)]
                offer, offer_created = PartSupplierOffer.objects.get_or_create(
                    part=part,
                    supplier=supplier,
                    defaults={
                        "supplier_code": f"{supplier.pk}-{number[-3:]}",
                        "purchase_price": cost,
                        "discount_percent": "5.00",
                        "minimum_order_quantity": "1.00",
                        "lead_time_days": 5 + index % 8,
                        "is_preferred": True,
                    },
                )
                offer.full_clean()
                counts["offers"] += int(offer_created)

            for index, model in enumerate(CAMPER_MODELS, start=1):
                vin = f"TST1RV{index:011d}"
                camper, created = Camper.objects.get_or_create(
                    workshop=workshop,
                    internal_number=f"DEMO-CAMP-{index:03d}",
                    defaults={
                        "owner": customers[(index - 1) % len(customers)],
                        "plate": f"TEST-RV-{index:03d}",
                        "vin": vin,
                        "brand": "Demo Coachworks",
                        "model": model,
                        "registration_date": date(REGISTRATION_YEARS[index - 1], 5 + index % 7, 10 + index % 17),
                        "engine_brand": "Sample Diesel",
                        "engine_model": f"SD-{200 + index}",
                        "engine_displacement": 2200 + (index % 4) * 200,
                        "engine_power": 110 + (index % 5) * 10,
                        "fuel_type": "DIESEL",
                        "transmission": "AUTOMATIC" if index % 2 == 0 else "MANUAL",
                        "body_brand": "Sample RV Works",
                        "body_model": model,
                        "seats": 4 + index % 3,
                        "sleeping_places": 4 + index % 4,
                        "length_mm": 6500 + index * 110,
                        "width_mm": 2300 + index * 10,
                        "height_mm": 2900 + index * 15,
                        "tare_weight": 3100 + index * 80,
                        "max_weight": 3500 + index * 100,
                        "mileage": 18000 + index * 7350,
                        "mileage_updated_at": date(2026, 11, 1),
                        "notes": "Fictional test vehicle; demo registration, VIN and specifications.",
                        "is_active": True,
                    },
                )
                camper.full_clean()
                counts["campers"] += int(created)

        self.stdout.write(self.style.SUCCESS(f"Officina: {workshop.name} ({workshop.slug})"))
        self.stdout.write(
            "Nuovi record - contatti: {contacts}, ricambi: {parts}, offerte: {offers}, camper: {campers}.".format(**counts)
        )
