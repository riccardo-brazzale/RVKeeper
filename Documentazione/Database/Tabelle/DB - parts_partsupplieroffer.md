---
title: "parts_partsupplieroffer"
tags:
  - rvkeeper
  - database-table
  - parts
---

# `parts_partsupplieroffer`

**Modello Django:** `parts.PartSupplierOffer`  
**Descrizione:** part supplier offer  
**App:** `parts`  
**Codice:** [parts/models.py](../../../parts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `part_id` | `part` | `ForeignKey` | NOT NULL -> [[DB - parts_part]] |
| `supplier_id` | `supplier` | `ForeignKey` | NOT NULL -> [[DB - clientandsuppliers_camperowner]] |
| `supplier_code` | `supplier_code` | `CharField` | blank |
| `purchase_price` | `purchase_price` | `DecimalField` | NOT NULL |
| `discount_percent` | `discount_percent` | `DecimalField` | NOT NULL |
| `minimum_order_quantity` | `minimum_order_quantity` | `DecimalField` | NOT NULL |
| `lead_time_days` | `lead_time_days` | `PositiveSmallIntegerField` | NULL, blank |
| `is_preferred` | `is_preferred` | `BooleanField` | NOT NULL |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `part` | [[DB - parts_part]] | `CASCADE` |
| `supplier` | [[DB - clientandsuppliers_camperowner]] | `PROTECT` |

## Riferimenti in ingresso

- [[DB - fleet_partsrequest]]. Campo `supplier_offer_id` (attributo `supplier_offer`).

## Vincoli applicativi/database

- `unique_supplier_offer_per_part`: part, supplier

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - parts_part]], [[DB - clientandsuppliers_camperowner]]
