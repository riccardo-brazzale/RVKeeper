---
title: "parts_jobpartusage"
tags:
  - rvkeeper
  - database-table
  - parts
---

# `parts_jobpartusage`

**Modello Django:** `parts.JobPartUsage`  
**Descrizione:** Ricambio utilizzato durante una lavorazione  
**App:** `parts`  
**Codice:** [parts/models.py](../../../parts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `job_id` | `job` | `ForeignKey` | NOT NULL -> [[DB - orders_job]] |
| `part_id` | `part` | `ForeignKey` | NOT NULL -> [[DB - parts_part]] |
| `quantity_used` | `quantity_used` | `DecimalField` | NOT NULL; maggiore di zero |
| `invoice_unit_price_override` | `invoice_unit_price_override` | `DecimalField` | NULL, blank |
| `used_by_id` | `used_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `created_at` | `created_at` | `DateTimeField` | NOT NULL |

## Vincoli

- `job_part_usage_quantity_positive`: `quantity_used > 0`.
- Il modello valida che ricambio, lavorazione e officina coincidano.

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `CASCADE` |
| `part` | [[DB - parts_part]] | `PROTECT` |
| `used_by` | [[DB - accounts_user]] | `SET_NULL` |

## Riferimenti in ingresso

- `orders_job`: relazione inversa `parts_used`.
- `parts_part`: relazione inversa `job_usages`.
