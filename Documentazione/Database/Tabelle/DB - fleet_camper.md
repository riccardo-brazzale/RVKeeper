---
title: "fleet_camper"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_camper`

**Modello Django:** `fleet.Camper`  
**Descrizione:** Camper  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `owner_id` | `owner` | `ForeignKey` | NULL, blank -> [[DB - clientandsuppliers_camperowner]] |
| `internal_number` | `internal_number` | `CharField` | NOT NULL |
| `plate` | `plate` | `CharField` | blank |
| `vin` | `vin` | `CharField` | blank |
| `brand` | `brand` | `CharField` | blank |
| `model` | `model` | `CharField` | blank |
| `registration_date` | `registration_date` | `DateField` | NULL, blank |
| `engine_brand` | `engine_brand` | `CharField` | blank |
| `engine_model` | `engine_model` | `CharField` | blank |
| `engine_displacement` | `engine_displacement` | `PositiveIntegerField` | NULL, blank |
| `engine_power` | `engine_power` | `DecimalField` | NULL, blank |
| `fuel_type` | `fuel_type` | `CharField` | blank; valori: Diesel, Benzina, Ibrido, Elettrico, Altro |
| `transmission` | `transmission` | `CharField` | blank; valori: Manuale, Automatico, Altro |
| `body_brand` | `body_brand` | `CharField` | blank |
| `body_model` | `body_model` | `CharField` | blank |
| `seats` | `seats` | `PositiveSmallIntegerField` | NULL, blank |
| `sleeping_places` | `sleeping_places` | `PositiveSmallIntegerField` | NULL, blank |
| `length_mm` | `length_mm` | `PositiveIntegerField` | NULL, blank |
| `width_mm` | `width_mm` | `PositiveIntegerField` | NULL, blank |
| `height_mm` | `height_mm` | `PositiveIntegerField` | NULL, blank |
| `tare_weight` | `tare_weight` | `PositiveIntegerField` | NULL, blank |
| `max_weight` | `max_weight` | `PositiveIntegerField` | NULL, blank |
| `mileage` | `mileage` | `PositiveIntegerField` | NULL, blank |
| `mileage_updated_at` | `mileage_updated_at` | `DateField` | NULL, blank |
| `notes` | `notes` | `TextField` | blank |
| `is_active` | `is_active` | `BooleanField` | NOT NULL |
| `created_at` | `created_at` | `DateTimeField` | blank |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `owner` | [[DB - clientandsuppliers_camperowner]] | `PROTECT` |

## Riferimenti in ingresso

- [[DB - fleet_camperphoto]]. Campo `camper_id` (attributo `camper`).
- [[DB - orders_workorder]]. Campo `vehicle_id` (attributo `vehicle`).
- [[DB - quotes_quote]]. Campo `vehicle_id` (attributo `vehicle`).

## Vincoli applicativi/database

- `unique_camper_number_per_workshop`: workshop, internal_number
- `unique_camper_plate_per_workshop`: workshop, plate
- `unique_camper_vin_per_workshop`: workshop, vin

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - clientandsuppliers_camperowner]]
