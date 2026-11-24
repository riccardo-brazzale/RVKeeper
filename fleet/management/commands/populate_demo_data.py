from datetime import date, timedelta
from decimal import Decimal
import random

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from clientandsuppliers.models import CamperOwner
from fleet.models import Camper
from orders.models import CustomerItemDiscount, Job, PriceList, PriceListItem, WorkOrder
from orders.pricing import ensure_workshop_price_list
from parts.models import Part, PartMovement, PartsRequest, PartSupplierOffer
from workshops.models import Workshop


DEMO_CUSTOMER_COUNT = 100
DEMO_PART_COUNT = 1000
DEMO_WORK_ORDER_COUNT = 10
DEMO_JOB_COUNT = 30
DEMO_PART_REQUEST_COUNT = 20
CLOSED_WORK_ORDER_COUNT = 3
PRICE_BENCHMARKS_AS_OF = date(2026, 11, 17)

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa",
    "Edward", "Deborah", "Ronald", "Stephanie", "Timothy", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
]

CONTACTS = [
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
]

CUSTOMER_NOTES = (
    "Profilo demo: proprietario di camper; preferisce preventivo scritto.",
    "Profilo demo: viaggiatore stagionale; aggiornamenti via email.",
    "Profilo demo: famiglia con camper; spiegazioni chiare sulle riparazioni.",
    "Profilo demo: lunga percorrenza; manutenzione preventiva e fattura dettagliata.",
    "Profilo demo: proprietario locale; contatto telefonico per urgenze.",
)

CAMPER_MODELS = [
    "Trailwind 21", "Mesa Touring 24", "Redwood Class C 26", "High Desert 28",
    "Blue Lake 22", "Canyon Explorer 25", "Pine Ridge 30", "Silver Pass 23",
    "Sagebrush 27", "Cascade Cruiser 29", "Juniper 24", "Summit Voyager 31",
]
REGISTRATION_YEARS = [2017, 2019, 2021, 2018, 2022, 2016, 2023, 2020, 2015, 2024, 2019, 2022]


# =============================================================================
# GENERATORI DI RICAMBI CON CODIFICA INTERNA INVENTATA
# =============================================================================

def _oil_filters():
    """FLT-01: filtri olio motore."""
    data = [
        ("spin-on", "3/4-16 UNF", 96, 93, "0.8", "Iveco Daily 2.3 Multijet II"),
        ("cartridge", "-", None, None, None, "Iveco Stralis Cursor 10/13"),
        ("spin-on", "M42x2", 318, 136, None, "Iveco Trakker NEF F4H"),
        ("spin-on", "M20x1.5", 85, 69, "1.0", "Alfa Romeo MiTo 1.4 TB"),
        ("spin-on", "18mm x 1.5", 86, 74, "0.9", "GM/Chevrolet small block"),
        ("spin-on", "13/16-16", 102, 76, "1.2", "Chevy/GMC 6.6L Duramax"),
        ("spin-on", "3/4-16", 90, 78, "1.0", "Honda Civic 1.6L"),
        ("spin-on", "20mm x 1.5", 95, 80, "1.1", "Ford 5.2L V8"),
        ("cartridge", "-", 67, None, None, "Toyota/Lexus 2.5L hybrid"),
        ("spin-on", "M27x2", 210, 108, "2.5", "MAN TGL/TGM D08"),
        ("spin-on", "M30x2", 260, 120, "2.5", "Mercedes Actros OM501"),
        ("cartridge", "-", 120, None, None, "Volvo D12/D13 Euro 5"),
    ]
    for ftype, thread, height, diameter, bypass, application in data:
        yield ftype, thread, height, diameter, bypass, application


def _air_filters():
    """FLT-02: filtri aria motore."""
    data = [
        ("panel", "3364cc Iveco NEF 58-79kW", "Iveco 237 VL"),
        ("panel", "Iveco NEF Euro 5", "Iveco 217/227/237"),
        ("panel", "Iveco Cursor 8", "Iveco EuroCargo"),
        ("panel", "Iveco Cursor 10/13", "Iveco Stralis"),
        ("panel", "VW/Audi/Seat/Skoda TDI", "VW Golf/Passat"),
        ("panel", "Mercedes-Benz OM651", "Mercedes Sprinter"),
        ("round", "Ford/Chevy/Dodge V8", "Pickup full-size"),
        ("panel", "Honda 1.6L", "Honda Civic"),
        ("panel", "GM/Ford/Chrysler", "Veicoli vari"),
        ("panel", "Toyota/Lexus 2.5L", "Toyota Camry/RAV4"),
        ("cylindrical", "Cummins ISB 6.7", "Dodge Ram 2500/3500"),
        ("panel", "MAN D20/D26", "MAN TGX/TGS"),
    ]
    for ftype, spec, application in data:
        yield ftype, spec, application


def _cabin_filters():
    """FLT-03: filtri abitacolo."""
    data = [
        ("biofunctional", "Iveco Cursor 11", "Iveco 460/480/500"),
        ("particulate", "Iveco Cursor 9", "Iveco 310/330/360"),
        ("activated carbon", "VW/Audi MQB", "VW Golf 7/Passat B8"),
        ("particulate", "BMW/Mercedes", "BMW Serie 3/Mercedes C"),
        ("particulate", "Honda/Toyota/Nissan", "Veicoli asiatici"),
        ("carbon", "Honda/Acura", "Honda Accord/CR-V"),
        ("antibacterial", "Mercedes Sprinter", "Sprinter 906/907"),
        ("particulate", "Ford Transit", "Transit 2014+"),
        ("activated carbon", "Fiat Ducato", "Ducato 2006+"),
        ("biofunctional", "MAN TGX", "MAN TGX/TGS"),
    ]
    for ftype, spec, application in data:
        yield ftype, spec, application


def _fuel_filters():
    """FLT-04: filtri carburante."""
    data = [
        ("spin-on", "Mercedes/BMW/VW", "Veicoli vari"),
        ("cartridge", "Iveco Cursor", "Iveco Stralis"),
        ("cartridge", "VW/Audi common rail", "VW/Audi 2.0 TDI"),
        ("spin-on", "Cummins/Duramax", "Pickup diesel"),
        ("spin-on", "Honda/Acura", "Honda Civic i-CTDi"),
        ("water separator", "Fiat Ducato 2.3", "Ducato 2006+"),
        ("cartridge", "Ford Transit 2.2", "Transit 2011+"),
        ("spin-on", "MAN D20/D26", "MAN TGX"),
    ]
    for ftype, spec, application in data:
        yield ftype, spec, application


def _spark_plugs():
    """FLT-05: candele."""
    data = [
        ("nickel", "M14x1.25", 19, "0.8", "Nissan Cabstar Z20S"),
        ("twin tip", "M14x1.25", 19, "1.1", "Nissan vari"),
        ("iridium", "M14x1.25", 19, "0.8", "Veicoli vari"),
        ("iridium", "M14x1.25", 19, "1.1", "Veicoli vari"),
        ("nickel", "M14x1.25", 19, "0.9", "VW/Audi/Seat"),
        ("double platinum", "M14x1.25", 19, "0.9", "BMW/Mercedes"),
        ("nickel", "M14x1.25", 19, "0.8", "Veicoli vari"),
        ("iridium", "M14x1.25", 26.5, "1.1", "Honda/Toyota"),
        ("platinum", "M12x1.25", 26.5, "1.0", "Ford EcoBoost"),
        ("nickel", "M14x1.25", 19, "0.9", "Ford/Chrysler"),
    ]
    for ptype, thread, reach, gap, application in data:
        yield ptype, thread, reach, gap, application


def _batteries():
    """FLT-06: batterie."""
    data = [
        ("EFB", "12V", "60Ah", "640A", "Veicoli con Start-Stop"),
        ("AGM", "12V", "70Ah", "760A", "Veicoli con Start-Stop"),
        ("standard", "12V", "70Ah", "640A", "Veicoli vari"),
        ("AGM", "12V", "80Ah", "800A", "Veicoli con Start-Stop"),
        ("EFB", "12V", "77Ah", "760A", "Veicoli con Start-Stop"),
        ("AGM", "12V", "95Ah", "850A", "Veicoli premium"),
        ("AGM spiral", "12V", "50Ah", "800A", "Avviamento/off-road"),
        ("AGM spiral", "12V", "55Ah", "750A", "Servizi/dual battery"),
        ("standard", "12V", "65Ah", "650A", "Veicoli vari"),
        ("AGM", "12V", "48Ah", "650A", "GM/Opel"),
        ("gel", "12V", "100Ah", "500A", "Camper/servizi ciclici"),
        ("LiFePO4", "12V", "100Ah", "N/A", "Camper/servizi ciclici"),
        ("LiFePO4", "12V", "200Ah", "N/A", "Camper/off-grid"),
        ("AGM", "12V", "100Ah", "800A", "Camper/servizi ciclici"),
    ]
    for btype, voltage, capacity, cca, application in data:
        yield btype, voltage, capacity, cca, application


def _brake_pads():
    """BRK-07: pastiglie freno."""
    data = [
        ("front", "Perrot", 149, 69, 18, "Veicoli commerciali leggeri"),
        ("front", "Bosch", 164.7, 66.5, 20.3, "Veicoli commerciali"),
        ("front", "Opel Movano Mk II", None, None, None, "Opel Movano 2015+"),
        ("front", "Citroen C4 II", None, None, None, "Citroen C4 2016+"),
        ("front", "Peugeot Boxer", None, None, None, "Peugeot Boxer 2009+"),
        ("front", "Perrot", 149, 69, 18, "LCV vari"),
        ("front", "Bosch", 164.7, 66.5, 20.3, "LCV vari"),
        ("front", "Bosch", 155, 68, 19, "Veicoli vari"),
        ("rear", "TRW", 120, 55, 16, "Veicoli vari"),
        ("front", "Bosch", 155, 68, 19, "Veicoli vari"),
        ("rear", "ATE", 123, 56, 17, "Veicoli vari"),
        ("front", "Brembo", 160, 70, 20, "Veicoli sportivi"),
    ]
    for position, system, width, height, thickness, application in data:
        yield position, system, width, height, thickness, application


def _brake_discs():
    """BRK-08: dischi freno."""
    data = [
        ("front", 280, 16, 141.5, "LCV vari"),
        ("rear", 289, 22, 84.6, "LCV 3500kg"),
        ("front", 257, 22, 100.0, "Fiat 500 2019+"),
        ("front", 300, 28, 120.0, "Mercedes Sprinter 2013+"),
        ("front", 280, 16, 141.5, "LCV vari"),
        ("rear", 289, 22, 84.6, "LCV vari"),
        ("front", 320, 30, 130.0, "Veicoli sportivi"),
        ("rear", 300, 22, 110.0, "Veicoli sportivi"),
        ("front", 350, 32, 150.0, "Camion leggeri"),
        ("rear", 330, 26, 140.0, "Camion leggeri"),
    ]
    for position, diameter, thickness, height, application in data:
        yield position, diameter, thickness, height, application


def _bolts():
    """HRD-11: bulloni esagonali UNI 5727 / DIN 931."""
    sizes = [
        ("M6", 20, "8.8"), ("M6", 30, "8.8"), ("M6", 40, "10.9"),
        ("M8", 25, "8.8"), ("M8", 40, "8.8"), ("M8", 60, "10.9"),
        ("M10", 30, "8.8"), ("M10", 50, "8.8"), ("M10", 80, "10.9"),
        ("M12", 40, "8.8"), ("M12", 60, "8.8"), ("M12", 100, "10.9"),
        ("M14", 50, "8.8"), ("M16", 60, "8.8"), ("M16", 100, "10.9"),
        ("M18", 70, "10.9"), ("M20", 80, "10.9"), ("M22", 90, "10.9"),
    ]
    for diameter, length, grade in sizes:
        yield diameter, length, grade


def _washers():
    """HRD-12: rondelle dentate DIN 6798A."""
    sizes = [("M5", "5.2", "10"), ("M6", "6.2", "11"), ("M8", "8.4", "15"),
             ("M10", "10.4", "18"), ("M12", "12.5", "21"), ("M14", "15.3", "24"),
             ("M16", "16.5", "26"), ("M18", "18.5", "29"), ("M20", "20.5", "32")]
    for thread, inner_d, outer_d in sizes:
        yield thread, inner_d, outer_d


def _clamps():
    """HRD-13: fascette tubo DIN 3017."""
    ranges = [("10-16", 9), ("12-20", 9), ("16-25", 9), ("20-32", 9),
              ("25-40", 9), ("32-50", 9), ("40-60", 9), ("50-70", 9),
              ("60-80", 9), ("70-90", 9), ("80-100", 9), ("100-120", 9),
              ("120-140", 9), ("140-160", 9)]
    for range_mm, width in ranges:
        yield range_mm, width


def _cables():
    """ELC-21: cavi elettrici."""
    data = [
        ("2x1.5", "bipolare rettangolare ADR", "camion ADR"),
        ("3x1.5", "multipolare 3 anime", "impianti ausiliari"),
        ("4x1", "multipolare 4 conduttori", "segnalazioni e comandi"),
        ("4x1.5", "multipolare 4 anime", "alimentazione ausiliaria"),
        ("5x1", "multipolare 5 conduttori", "comandi multipli"),
        ("6x1+1x2.5", "multipolare 7 anime", "rimorchi e semirimorchi"),
        ("2x1", "bipolare guaina neoprene", "uso generale automotive"),
        ("1x2.5", "unipolare rosso", "alimentazioni positive"),
        ("1x2.5", "unipolare nero", "masse e negativi"),
        ("1x4", "unipolare rosso", "alimentazioni ad alta corrente"),
        ("1x4", "unipolare nero", "masse ad alta corrente"),
        ("2x2.5", "bipolare", "prese 12V ausiliarie"),
    ]
    for section, ctype, application in data:
        yield section, ctype, application


def _fuses():
    """ELC-22: fusibili a lama."""
    amps = ["2A", "3A", "5A", "7.5A", "10A", "15A", "20A", "25A",
            "30A", "35A", "40A"]
    types = ["standard (APR/ATO)", "mini (ATM/ATO)", "maxi (AMT)"]
    for amp in amps:
        for ftype in types:
            yield amp, ftype


def _breakers():
    """ELC-23: interruttori automatici (circuit breaker)."""
    amps = ["25A", "30A", "35A", "40A", "50A", "60A", "70A", "80A",
            "90A", "100A", "110A", "120A", "135A", "150A"]
    types = ["CB184F Type III", "CB185 Type III", "CB285 Type III"]
    for amp in amps:
        for btype in types:
            yield amp, btype


def _solar_panels():
    """SOL-31: pannelli solari per camper."""
    data = [
        ("flessibile back contact", 155, "12V", "22.40V", "8.57A", "1400x515x30"),
        ("flessibile back contact", 110, "12V", "21.5V", "6.8A", "1200x500x30"),
        ("flessibile ETFE", 80, "12V", "21.9V", "4.8A", "1050x540x2"),
        ("flessibile ETFE", 110, "12V", "21.9V", "6.32A", "1250x560x2"),
        ("flessibile ETFE", 125, "12V", "23.36V", "6.94A", "1350x600x2"),
        ("flessibile ETFE", 150, "12V", "29.2V", "6.41A", "1450x680x2"),
        ("flessibile MHD", 110, "12V", "21.2V", "6.48A", "1080x540x2"),
        ("flessibile MHD", 150, "12V", "22.0V", "8.55A", "1440x560x2"),
        ("flessibile MHD", 200, "12V", "28.8V", "8.69A", "1435x710x2"),
        ("rigido policristallino", 100, "12V", "21.8V", "6.1A", "1020x670x35"),
        ("rigido monocristallino", 160, "12V", "22.5V", "8.9A", "1480x670x35"),
        ("rigido monocristallino", 200, "12V", "23.0V", "10.4A", "1580x808x35"),
    ]
    for ptype, watts, voltage, voc, isc, dimensions in data:
        yield ptype, watts, voltage, voc, isc, dimensions


def _awnings():
    """AWN-41: tendalini per camper."""
    data = [
        ("parete", "Royal Grey", 350),
        ("parete", "Royal Grey", 400),
        ("parete", "Royal Grey", 450),
        ("parete cassonetto maggiorato", "Royal Grey", 450),
        ("parete cassonetto maggiorato", "Royal Grey", 500),
        ("parete cassonetto maggiorato", "Royal Grey", 550),
        ("tetto", "Royal Grey", 319),
        ("tetto", "Royal Grey", 369),
        ("tetto", "Royal Grey", 399),
        ("tetto", "Royal Grey", 400),
        ("tetto", "Polar White", 370),
        ("parete", "Polar White", 420),
    ]
    for mount, color, length_cm in data:
        yield mount, color, length_cm


def _toilet_parts():
    """WCS-51: ricambi WC chimici."""
    data = [
        ("guarnizione sfiato automatico cassetta", "C2, C3, C4, C-200"),
        ("guarnizione base WC a cassetta", "C2, C3, C4"),
        ("valvola a sfera per cassetta", "C2, C3, C4"),
        ("guarnizione oblò cassetta", "C200, C250, C260"),
        ("guarnizione ingresso cassetta", "CTS-3110, CTS-4110"),
        ("cassetta WC completa", "CTS-3110, CTS-4110"),
        ("guarnizione scarico cassetta", "Sealand Traveler"),
        ("liquido Aqua Kem Blue 2L", "tutti i WC chimici"),
        ("liquido Aqua Kem Green 2L", "tutti i WC chimici"),
        ("liquido Aqua Rinse 2L", "tutti i WC chimici"),
        ("pompa di scarico 12V", "C200, C250, C260"),
        ("sensore livello cassetta", "CTS-3110, CTS-4110"),
    ]
    for part_type, compatibility in data:
        yield part_type, compatibility


# =============================================================================
# COSTRUZIONE DEL CATALOGO CON CODIFICA INTERNA
# =============================================================================

def build_part_catalog():
    """Costruisce 1000 ricambi con codifica interna inventata e descrizioni
    tecniche univoche per categoria."""
    catalog = []
    rng = random.Random(20261117)

    def add(cat_code, group_code, name, description, unit, base_price):
        progressivo = sum(1 for c in catalog if c["part_number"].startswith(f"{cat_code}-{group_code}-")) + 1
        part_number = f"{cat_code}-{group_code}-{progressivo:04d}"
        catalog.append({
            "part_number": part_number,
            "name": name,
            "description": description,
            "unit": unit,
            "base_price": base_price,
        })

    # --- FLT-01 filtri olio ---------------------------------------------------
    for i, (ftype, thread, height, diameter, bypass, application) in enumerate(_oil_filters(), start=1):
        specs = [f"Tipo: {ftype}"]
        if thread and thread != "-":
            specs.append(f"Filettatura: {thread}")
        if height:
            specs.append(f"Altezza: {height} mm")
        if diameter:
            specs.append(f"Diametro: {diameter} mm")
        if bypass:
            specs.append(f"Pressione bypass: {bypass} bar")
        desc = (
            f"Filtro olio motore, configurazione {i:02d}. {' | '.join(specs)}. "
            f"Applicazione tipica: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}. "
            f"Verificare sempre la compatibilità con il veicolo prima dell'ordine."
        )
        add("FLT", "01", f"Filtro olio motore cfg {i:02d}", desc, "each",
            Decimal("8.50") + Decimal(i % 5) * Decimal("2"))

    # --- FLT-02 filtri aria ---------------------------------------------------
    for i, (ftype, spec, application) in enumerate(_air_filters(), start=1):
        desc = (
            f"Filtro aria motore, configurazione {i:02d}. Tipo: {ftype}. "
            f"Specifica: {spec}. Applicazione tipica: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("FLT", "02", f"Filtro aria motore cfg {i:02d}", desc, "each",
            Decimal("12.00") + Decimal(i % 6) * Decimal("1.5"))

    # --- FLT-03 filtri abitacolo ---------------------------------------------
    for i, (ftype, spec, application) in enumerate(_cabin_filters(), start=1):
        desc = (
            f"Filtro abitacolo, configurazione {i:02d}. Tipo: {ftype}. "
            f"Specifica: {spec}. Applicazione tipica: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("FLT", "03", f"Filtro abitacolo cfg {i:02d}", desc, "each",
            Decimal("15.00") + Decimal(i % 5) * Decimal("2"))

    # --- FLT-04 filtri carburante --------------------------------------------
    for i, (ftype, spec, application) in enumerate(_fuel_filters(), start=1):
        desc = (
            f"Filtro carburante, configurazione {i:02d}. Tipo: {ftype}. "
            f"Specifica: {spec}. Applicazione tipica: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("FLT", "04", f"Filtro carburante cfg {i:02d}", desc, "each",
            Decimal("18.00") + Decimal(i % 6) * Decimal("2.5"))

    # --- FLT-05 candele -------------------------------------------------------
    for i, (ptype, thread, reach, gap, application) in enumerate(_spark_plugs(), start=1):
        desc = (
            f"Candela di accensione, configurazione {i:02d}. Tipo: {ptype}. "
            f"Filettatura: {thread}. Lunghezza filettatura: {reach} mm. "
            f"Distanza elettrodi: {gap} mm. Applicazione tipica: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("FLT", "05", f"Candela accensione cfg {i:02d}", desc, "each",
            Decimal("4.50") + Decimal(i % 7) * Decimal("0.8"))

    # --- FLT-06 batterie ------------------------------------------------------
    for i, (btype, voltage, capacity, cca, application) in enumerate(_batteries(), start=1):
        desc = (
            f"Batteria, configurazione {i:02d}. Tipo: {btype}. Tensione: {voltage}. "
            f"Capacità: {capacity}. Corrente avviamento a freddo: {cca}. "
            f"Applicazione: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("FLT", "06", f"Batteria cfg {i:02d}", desc, "each",
            Decimal("65.00") + Decimal(i % 8) * Decimal("8"))

    # --- BRK-07 pastiglie -----------------------------------------------------
    for i, (position, system, width, height, thickness, application) in enumerate(_brake_pads(), start=1):
        specs = [f"Posizione: {position}", f"Sistema: {system}"]
        if width:
            specs.append(f"Larghezza: {width} mm")
        if height:
            specs.append(f"Altezza: {height} mm")
        if thickness:
            specs.append(f"Spessore: {thickness} mm")
        desc = (
            f"Set pastiglie freno, configurazione {i:02d}. {' | '.join(specs)}. "
            f"Applicazione: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("BRK", "07", f"Pastiglie freno cfg {i:02d}", desc, "set",
            Decimal("28.00") + Decimal(i % 6) * Decimal("4"))

    # --- BRK-08 dischi --------------------------------------------------------
    for i, (position, diameter, thickness, height, application) in enumerate(_brake_discs(), start=1):
        desc = (
            f"Disco freno, configurazione {i:02d}. Posizione: {position}. "
            f"Diametro: {diameter} mm. Spessore: {thickness} mm. "
            f"Altezza: {height} mm. Applicazione: {application}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("BRK", "08", f"Disco freno cfg {i:02d}", desc, "each",
            Decimal("45.00") + Decimal(i % 6) * Decimal("6"))

    # --- HRD-11 bulloni -------------------------------------------------------
    for i, (diameter, length, grade) in enumerate(_bolts(), start=1):
        desc = (
            f"Bullone a testa esagonale, filettatura metrica ISO passo grosso. "
            f"Diametro {diameter}, lunghezza {length} mm, classe di resistenza {grade}. "
            f"Conforme UNI 5727. Zincato. Adatto per assemblaggi strutturali su telai, "
            f"carrozzerie e componenti meccanici di camper e veicoli commerciali. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("HRD", "11", f"Bullone esagonale {diameter}x{length} {grade}", desc, "pz",
            Decimal("0.45") + Decimal(str(length)) / 100)

    # --- HRD-12 rondelle ------------------------------------------------------
    for i, (thread, inner_d, outer_d) in enumerate(_washers(), start=1):
        desc = (
            f"Rondella dentata interna in acciaio inox. Per filettatura {thread}, "
            f"diametro interno {inner_d} mm, diametro esterno {outer_d} mm. "
            f"Previene allentamenti su giunzioni soggette a vibrazioni. "
            f"Confezione da 20 pezzi. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("HRD", "12", f"Rondella dentata {thread}", desc, "conf. 20 pz",
            Decimal("2.50") + Decimal(i % 5) * Decimal("0.3"))

    # --- HRD-13 fascette ------------------------------------------------------
    for i, (range_mm, width) in enumerate(_clamps(), start=1):
        desc = (
            f"Fascetta stringitubo in acciaio inox, conforme DIN 3017 - W2. "
            f"Intervallo di serraggio {range_mm} mm, larghezza nastro {width} mm. "
            f"Adatta per fissaggio di tubi flessibili, manicotti di raffreddamento, "
            f"scarichi e impianti idraulici su veicoli e camper. "
            f"Confezione da 5 pezzi. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("HRD", "13", f"Fascetta tubo {range_mm} mm", desc, "conf. 5 pz",
            Decimal("3.80") + Decimal(i % 6) * Decimal("0.4"))

    # --- ELC-21 cavi ----------------------------------------------------------
    for i, (section, ctype, application) in enumerate(_cables(), start=1):
        desc = (
            f"Cavo elettrico multipolare, sezione {section} mm², {ctype}. "
            f"Guaina esterna in PVC o neoprene nero. Tensione nominale 12/24V. "
            f"Impiego tipico: {application} su camion, rimorchi e camper. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("ELC", "21", f"Cavo elettrico {section} mm²", desc, "bobina",
            Decimal("45.00") + Decimal(str(i % 8) * 8))

    # --- ELC-22 fusibili ------------------------------------------------------
    for i, (amp, ftype) in enumerate(_fuses(), start=1):
        desc = (
            f"Fusibile a lama per impianti elettrici 12/24V. Amperaggio {amp}, "
            f"tipo {ftype}. Corpo in plastica ignifuga, contatti in lega di zinco. "
            f"Identificazione tramite codice colore. Adatto per auto, camion, camper, "
            f"roulotte e imbarcazioni. Confezione da 10 pezzi. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("ELC", "22", f"Fusibile {amp} {ftype}", desc, "conf. 10 pz",
            Decimal("3.50") + Decimal(i % 5) * Decimal("0.2"))

    # --- ELC-23 interruttori --------------------------------------------------
    for i, (amp, btype) in enumerate(_breakers(), start=1):
        desc = (
            f"Interruttore automatico (circuit breaker) {btype}. Corrente nominale {amp}, "
            f"tensione 48VDC, potere di interruzione 3kA. Riarmo manuale, protezione "
            f"da sovracorrente per circuiti ausiliari di camion, camper, autobus e "
            f"applicazioni marine. Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("ELC", "23", f"Interruttore automatico {amp} {btype}", desc, "each",
            Decimal("18.00") + Decimal(i % 6) * Decimal("2.5"))

    # --- SOL-31 pannelli solari -----------------------------------------------
    for i, (ptype, watts, voltage, voc, isc, dimensions) in enumerate(_solar_panels(), start=1):
        desc = (
            f"Pannello solare, potenza massima {watts}W, tensione nominale {voltage}, "
            f"tensione circuito aperto {voc}, corrente corto circuito {isc}. "
            f"Dimensioni: {dimensions} mm. Tipo: {ptype}. Celle solari ad alta efficienza "
            f"con protezione IP67 e resistenza UV. Adatto per installazione permanente "
            f"su camper, caravan e veicoli off-grid. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("SOL", "31", f"Pannello solare {watts}W {ptype}", desc, "each",
            Decimal("180.00") + Decimal(str(watts * 1.2)))

    # --- AWN-41 tendalini -----------------------------------------------------
    for i, (mount, color, length_cm) in enumerate(_awnings(), start=1):
        desc = (
            f"Tendalino automatico. Montaggio: {mount}. Lunghezza {length_cm} cm, "
            f"colore {color}. Azionamento elettrico 12Vcc, senza paline, con bracci "
            f"articolati. Cassonetto in alluminio e telo in tessuto acrilico resistente "
            f"ai raggi UV. Adatto per camper e caravan. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("AWN", "41", f"Tendalino {mount} {length_cm}cm {color}", desc, "each",
            Decimal("850.00") + Decimal(str(length_cm * 1.5)))

    # --- WCS-51 ricambi WC ----------------------------------------------------
    for i, (part_type, compatibility) in enumerate(_toilet_parts(), start=1):
        desc = (
            f"Ricambio per WC chimico a cassetta: {part_type}. "
            f"Compatibile con modelli {compatibility}. Materiale originale o equivalente "
            f"di alta qualità per garantire tenuta e funzionamento corretto del sistema "
            f"di scarico. Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add("WCS", "51", f"Ricambio WC {part_type}", desc, "each",
            Decimal("12.00") + Decimal(i % 6) * Decimal("3"))

    # --- Espansione controllata fino a 1000 record ----------------------------
    # Ripete le categorie con varianti numerate, mantenendo univocità della
    # descrizione (aggiunge "Variante N" e un dettaglio tecnico diverso).
    base_templates = [
        ("FLT", "01", "Filtro olio motore", "each", "8.50"),
        ("FLT", "02", "Filtro aria motore", "each", "12.00"),
        ("FLT", "03", "Filtro abitacolo", "each", "15.00"),
        ("FLT", "04", "Filtro carburante", "each", "18.00"),
        ("FLT", "05", "Candela accensione", "each", "4.50"),
        ("FLT", "06", "Batteria", "each", "65.00"),
        ("BRK", "07", "Pastiglie freno", "set", "28.00"),
        ("BRK", "08", "Disco freno", "each", "45.00"),
        ("HRD", "11", "Bullone esagonale", "pz", "0.45"),
        ("HRD", "12", "Rondella dentata", "conf. 20 pz", "2.50"),
        ("HRD", "13", "Fascetta tubo", "conf. 5 pz", "3.80"),
        ("ELC", "21", "Cavo elettrico", "bobina", "45.00"),
        ("ELC", "22", "Fusibile", "conf. 10 pz", "3.50"),
        ("ELC", "23", "Interruttore automatico", "each", "18.00"),
        ("SOL", "31", "Pannello solare", "each", "180.00"),
        ("AWN", "41", "Tendalino", "each", "850.00"),
        ("WCS", "51", "Ricambio WC", "each", "12.00"),
    ]
    extra_details = [
        "Trattamento superficiale anticorrosione.",
        "Conforme normative SAE/DIN applicabili.",
        "Confezionamento industriale.",
        "Tolleranze secondo specifica produttore.",
        "Adatto a condizioni di esercizio gravose.",
        "Materiale riciclabile.",
        "Etichettatura con lotto di produzione.",
        "Stoccaggio consigliato in ambiente asciutto.",
        "Compatibile con ricambi equivalenti aftermarket.",
        "Verificare coppia di serraggio in manuale officina.",
    ]
    idx = 0
    while len(catalog) < DEMO_PART_COUNT:
        cat_code, group_code, base_name, unit, base_price = base_templates[idx % len(base_templates)]
        idx += 1
        variant_no = len(catalog) + 1
        detail = extra_details[variant_no % len(extra_details)]
        desc = (
            f"{base_name}, variante {variant_no:04d}. {detail} "
            f"Specifica tecnica generata per catalogo interno: "
            f"articolo di categoria {cat_code}/{group_code}. "
            f"Riferimento tecnico del {PRICE_BENCHMARKS_AS_OF.isoformat()}."
        )
        add(cat_code, group_code, f"{base_name} variante {variant_no:04d}",
            desc, unit, Decimal(base_price) + Decimal(str((variant_no % 10) * 0.5)))

    rng.shuffle(catalog)
    return catalog[:DEMO_PART_COUNT]


def generated_parts():
    """Restituisce tuple pronte per Part.objects.get_or_create."""
    for index, item in enumerate(build_part_catalog(), start=1):
        cost = item["base_price"]
        sale = (cost * Decimal("1.35")).quantize(Decimal("0.01"))
        yield (
            item["part_number"],
            item["name"],
            item["description"],
            item["unit"],
            str(cost),
            str(sale),
            5 + index % 40,
            1 + index % 8,
            f"WH-{(index - 1) // 80 + 1:02d}-{index % 80:02d}",
        )


def generated_customer_contacts():
    fixed_customers = sum(
        row["kind"] in ("customer", "both") for row in CONTACTS
    )
    generated_count = max(DEMO_CUSTOMER_COUNT - fixed_customers, 0)
    for index in range(1, generated_count + 1):
        rng = random.Random(index * 7)
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        yield {
            "kind": "customer",
            "first_name": first,
            "last_name": last,
            "phone": f"+1-800-555-{index:04d}",
            "email": f"{first.lower()}.{last.lower()}.{index:03d}@contacts.example",
            "address": f"{100 + index} {rng.choice(['Oak', 'Maple', 'Cedar', 'Pine'])} Street",
            "postal_code": f"{10000 + index:05d}",
            "city": rng.choice(["Springfield", "Riverside", "Franklin", "Greenville"]),
        }


class Command(BaseCommand):
    help = (
        "Popola un'officina USA con 100 clienti demo, 1000 ricambi auto/camion/RV "
        "con codifica interna, camper, ordini, lavorazioni e richieste di magazzino "
        "senza duplicare i record."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workshop", help="Slug dell'officina USA da popolare.")

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
            raise CommandError("Officina attiva non trovata.")

        counts = {
            "contacts": 0, "customers": 0, "parts": 0, "offers": 0,
            "campers": 0, "work_orders": 0, "jobs": 0, "parts_requests": 0,
        }
        demo_customer_emails = {row["email"] for row in CONTACTS if row["kind"] in ("customer", "both")}
        demo_customer_emails.update(row["email"] for row in generated_customer_contacts())
        demo_part_numbers = {row[0] for row in generated_parts()}

        with transaction.atomic():
            # --- CONTATTI ---
            customer_profile_index = 0
            for row in (*CONTACTS, *generated_customer_contacts()):
                data = dict(row)
                is_company = data.pop("is_company", False)
                defaults = {
                    **data,
                    "is_company": is_company,
                    "country": "US",
                    "notes": "Fictional sample supplier record generated for testing.",
                }
                if row["kind"] in ("customer", "both"):
                    defaults["notes"] = CUSTOMER_NOTES[customer_profile_index % len(CUSTOMER_NOTES)]
                    customer_profile_index += 1
                contact, created = CamperOwner.objects.get_or_create(
                    workshop=workshop, email=row["email"], defaults=defaults,
                )
                if not created and contact.is_customer and contact.notes != defaults["notes"]:
                    contact.notes = defaults["notes"]
                    contact.save(update_fields=("notes",))
                contact.full_clean()
                counts["contacts"] += int(created)
                counts["customers"] += int(created and contact.is_customer)

            suppliers = list(
                CamperOwner.objects.filter(workshop=workshop, kind__in=("supplier", "both")).order_by("email")
            )
            customers = list(
                CamperOwner.objects.filter(workshop=workshop, kind__in=("customer", "both")).order_by("email")
            )
            if not suppliers or not customers:
                raise CommandError("Servono clienti e fornitori nell'officina.")

            # --- RICAMBI ---
            price_list = PriceList.objects.filter(workshop=workshop, is_default=True).first()
            if price_list is None:
                code = "CLIENTE"
                suffix = 1
                while PriceList.objects.filter(workshop=workshop, code=code).exists():
                    code = f"CLIENTE-{suffix}"
                    suffix += 1
                price_list = PriceList.objects.create(
                    workshop=workshop,
                    code=code,
                    name="Listino Cliente",
                    is_default=True,
                )
            elif price_list.name != "Listino Cliente" or price_list.code != "CLIENTE":
                price_list.name = "Listino Cliente"
                price_list.code = "CLIENTE"
                price_list.save(update_fields=("name", "code"))
            for customer in customers:
                if customer.price_list_id != price_list.pk:
                    customer.price_list = price_list
                    customer.save(update_fields=("price_list",))
            parts = []
            for index, row in enumerate(generated_parts(), start=1):
                number, name, description, unit, cost, sale, quantity, min_stock, location = row
                defaults = {
                    "name": name, "description": description, "unit": unit,
                    "cost_price": cost, "standard_minutes": 15,
                    "quantity": quantity, "min_stock": min_stock, "location": location,
                }
                part, created = Part.objects.get_or_create(
                    workshop=workshop, part_number=number, defaults=defaults,
                )
                if not created:
                    updated_fields = []
                    for field_name in (
                        "name", "description", "unit", "cost_price",
                        "standard_minutes", "min_stock", "location",
                    ):
                        if getattr(part, field_name) != defaults[field_name]:
                            setattr(part, field_name, defaults[field_name])
                            updated_fields.append(field_name)
                    if updated_fields:
                        part.save(update_fields=(*updated_fields, "updated_at"))
                PriceListItem.objects.update_or_create(
                    price_list=price_list,
                    part=part,
                    defaults={"unit_price": sale},
                )
                part.full_clean()
                counts["parts"] += int(created)
                parts.append(part)

                supplier = suppliers[index % len(suppliers)]
                offer, offer_created = PartSupplierOffer.objects.get_or_create(
                    part=part, supplier=supplier,
                    defaults={
                        "supplier_code": f"{supplier.pk}-{number[-4:]}",
                        "purchase_price": cost,
                        "discount_percent": "5.00",
                        "minimum_order_quantity": "1.00",
                        "lead_time_days": 3 + index % 10,
                        "is_preferred": True,
                    },
                )
                offer_updates = []
                if not offer.supplier_code:
                    offer.supplier_code = f"{supplier.pk}-{number[-4:]}"
                    offer_updates.append("supplier_code")
                if not offer_created and offer.purchase_price != cost:
                    offer.purchase_price = cost
                    offer_updates.append("purchase_price")
                if offer_updates:
                    offer.save(update_fields=(*offer_updates, "updated_at"))
                offer.full_clean()
                counts["offers"] += int(offer_created)

            ensure_workshop_price_list(workshop)
            exception_rng = random.Random(f"{workshop.pk}:price-list-exceptions")
            for customer in exception_rng.sample(customers, min(3, len(customers))):
                exception_list = PriceList.objects.filter(workshop=workshop, customer=customer).first()
                if exception_list is None:
                    exception_list, _ = PriceList.objects.get_or_create(
                        workshop=workshop,
                        code=customer.customer_code,
                        defaults={
                            "name": f"Eccezioni demo · {customer.customer_code}",
                            "customer": customer,
                        },
                    )
                elif exception_list.code != customer.customer_code:
                    exception_list.code = customer.customer_code
                    exception_list.save(update_fields=("code",))
                if exception_list.customer_id != customer.pk:
                    exception_list.customer = customer
                    exception_list.save(update_fields=("customer",))
                for part in exception_rng.sample(parts, min(3, len(parts))):
                    CustomerItemDiscount.objects.update_or_create(
                        customer=customer,
                        part=part,
                        defaults={"discount_percent": Decimal("5.00")},
                    )

            # --- CAMPER ---
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

            demo_campers = list(
                Camper.objects.filter(
                    workshop=workshop,
                    internal_number__in=[
                        f"DEMO-CAMP-{index:03d}" for index in range(1, len(CAMPER_MODELS) + 1)
                    ],
                ).select_related("owner").order_by("internal_number")
            )
            if len(demo_campers) < DEMO_WORK_ORDER_COUNT:
                raise CommandError("Impossibile creare gli ordini demo: mancano camper demo.")

            # --- ORDINI E LAVORAZIONI ---
            now = timezone.now()
            demo_jobs = []
            for order_index in range(1, DEMO_WORK_ORDER_COUNT + 1):
                camper = demo_campers[(order_index - 1) % len(demo_campers)]
                is_closed = order_index <= CLOSED_WORK_ORDER_COUNT
                work_order, created = WorkOrder.objects.get_or_create(
                    workshop=workshop,
                    ro_number=f"DEMO-RO-{order_index:03d}",
                    defaults={
                        "customer": camper.owner,
                        "vehicle": camper,
                        "customer_name": str(camper.owner),
                        "customer_phone": camper.owner.phone,
                        "customer_email": camper.owner.email,
                        "year": str(camper.registration_date.year) if camper.registration_date else "",
                        "make": camper.brand,
                        "model": camper.model,
                        "odometer": camper.mileage,
                        "work_classification": "customer_pay",
                        "status": "completed" if is_closed else ("open" if order_index % 2 else "in_progress"),
                        "completed_at": now - timedelta(days=order_index) if is_closed else None,
                        "reception_notes": f"Fictional demo work order {order_index:03d}.",
                    },
                )
                work_order.full_clean()
                counts["work_orders"] += int(created)

                for job_number in range(1, DEMO_JOB_COUNT // DEMO_WORK_ORDER_COUNT + 1):
                    if is_closed:
                        job_status = "completed"
                    elif job_number == 1:
                        job_status = "waiting_parts"
                    elif job_number == 2:
                        job_status = "in_progress"
                    else:
                        job_status = "not_started"
                    job, job_created = Job.objects.get_or_create(
                        workshop=workshop,
                        work_order=work_order,
                        job_number=job_number,
                        defaults={
                            "title": (
                                "Demo maintenance inspection" if job_number == 1 else
                                "Demo component replacement" if job_number == 2 else
                                "Demo final quality check"
                            ),
                            "description": "Fictional sample work for demonstrating the workshop workflow.",
                            "category": "customer_pay",
                            "status": job_status,
                            "standard_minutes": 45 + job_number * 15,
                            "started_at": now - timedelta(days=order_index) if job_status != "not_started" else None,
                            "completed_at": now - timedelta(days=order_index) if is_closed else None,
                        },
                    )
                    job.full_clean()
                    counts["jobs"] += int(job_created)
                    demo_jobs.append(job)

            # --- RICHIESTE MAGAZZINO ---
            request_parts = parts[100:100 + DEMO_PART_REQUEST_COUNT]
            for request_index in range(1, DEMO_PART_REQUEST_COUNT + 1):
                order_index = (request_index - 1) // 2
                job_index = order_index * 3 + (request_index - 1) % 2
                work_order = demo_jobs[job_index].work_order
                part = request_parts[request_index - 1]
                delivered = (
                    order_index < CLOSED_WORK_ORDER_COUNT
                    or request_index % 2 == 0
                )
                request_number = f"DEMO-REQ-{request_index:03d}"
                quantity = Decimal("1.00")
                request, created = PartsRequest.objects.get_or_create(
                    workshop=workshop,
                    order_number=request_number,
                    defaults={
                        "work_order": work_order,
                        "job": demo_jobs[job_index],
                        "part": part,
                        "unit": part.unit,
                        "quantity_requested": quantity,
                        "quantity_delivered": quantity if delivered else Decimal("0.00"),
                        "unit_delivered": part.unit if delivered else "",
                        "status": "delivered" if delivered else "pending",
                        "delivered_at": now - timedelta(days=request_index) if delivered else None,
                        "inventory_applied": delivered,
                        "notes": f"Fictional demo warehouse request {request_number}.",
                    },
                )
                request.full_clean()
                counts["parts_requests"] += int(created)

                if created and delivered:
                    _, movement_created = PartMovement.objects.get_or_create(
                        workshop=workshop,
                        part=part,
                        work_order=work_order,
                        movement_type="out",
                        note=f"Demo delivery {request_number}",
                        defaults={"quantity": quantity, "unit_cost": part.cost_price},
                    )
                    if movement_created:
                        part.quantity -= quantity
                        part.save(update_fields=("quantity", "updated_at"))

            # --- VERIFICHE FINALI ---
            actual_demo_customers = CamperOwner.objects.filter(
                workshop=workshop,
                email__in=demo_customer_emails,
                kind__in=("customer", "both"),
            ).count()
            if actual_demo_customers != DEMO_CUSTOMER_COUNT:
                raise CommandError(
                    f"Attesi {DEMO_CUSTOMER_COUNT} clienti demo, trovati {actual_demo_customers}."
                )
            expected_counts = (
                ("ricambi",
                 Part.objects.filter(workshop=workshop, part_number__in=demo_part_numbers).count(),
                 DEMO_PART_COUNT),
                ("ordini",
                 WorkOrder.objects.filter(workshop=workshop, ro_number__startswith="DEMO-RO-").count(),
                 DEMO_WORK_ORDER_COUNT),
                ("lavorazioni",
                 Job.objects.filter(workshop=workshop, work_order__ro_number__startswith="DEMO-RO-").count(),
                 DEMO_JOB_COUNT),
                ("richieste magazzino",
                 PartsRequest.objects.filter(workshop=workshop, order_number__startswith="DEMO-REQ-").count(),
                 DEMO_PART_REQUEST_COUNT),
            )
            for label, actual, expected in expected_counts:
                if actual != expected:
                    raise CommandError(f"Attesi {expected} {label} demo, trovati {actual}.")

            counts.update(
                demo_customers_total=actual_demo_customers,
                demo_parts_total=expected_counts[0][1],
                demo_work_orders_total=expected_counts[1][1],
                demo_jobs_total=expected_counts[2][1],
                demo_parts_requests_total=expected_counts[3][1],
                demo_closed_orders=WorkOrder.objects.filter(
                    workshop=workshop, ro_number__startswith="DEMO-RO-", status="completed",
                ).count(),
                demo_delivered_requests=PartsRequest.objects.filter(
                    workshop=workshop, order_number__startswith="DEMO-REQ-", status="delivered",
                ).count(),
                demo_open_requests=PartsRequest.objects.filter(
                    workshop=workshop, order_number__startswith="DEMO-REQ-", status="pending",
                ).count(),
            )

        self.stdout.write(self.style.SUCCESS(f"Officina: {workshop.name} ({workshop.slug})"))
        self.stdout.write(
            "Nuovi record - contatti: {contacts}, ricambi: {parts}, offerte: {offers}, camper: {campers}, "
            "ordini: {work_orders}, lavorazioni: {jobs}, richieste: {parts_requests}. "
            "Totale demo - clienti: {demo_customers_total}, ricambi: {demo_parts_total}, "
            "ordini: {demo_work_orders_total} (chiusi: {demo_closed_orders}), "
            "lavorazioni: {demo_jobs_total}, richieste magazzino: {demo_parts_requests_total} "
            "({demo_delivered_requests} consegnate, {demo_open_requests} aperte).".format(**counts)
        )
