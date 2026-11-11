---
title: "parts_part"
tags:
  - rvkeeper
  - database-table
  - parts
---

# `parts_part`

**Modello Django:** `parts.Part`  
**Descrizione:** part  
**App:** `parts`  
**Codice:** [parts/models.py](../../../parts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `part_number` | `part_number` | `CharField` | NOT NULL |
| `name` | `name` | `CharField` | NOT NULL |
| `description` | `description` | `TextField` | blank |
| `unit` | `unit` | `CharField` | NOT NULL |
| `cost_price` | `cost_price` | `DecimalField` | NOT NULL |
| `sale_price` | `sale_price` | `DecimalField` | NOT NULL |
| `standard_minutes` | `standard_minutes` | `PositiveIntegerField` | NOT NULL |
| `quantity` | `quantity` | `DecimalField` | NOT NULL |
| `min_stock` | `min_stock` | `DecimalField` | NOT NULL |
| `location` | `location` | `CharField` | blank |
| `created_at` | `created_at` | `DateTimeField` | blank |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |

## Riferimenti in ingresso

- [[DB - fleet_partsrequest]]. Campo `part_id` (attributo `part`).
- [[DB - parts_partsupplieroffer]]. Campo `part_id` (attributo `part`).
- [[DB - parts_partdocument]]. Campo `part_id` (attributo `part`).
- [[DB - parts_partmovement]]. Campo `part_id` (attributo `part`).
- [[DB - quotes_quoteline]]. Campo `part_id` (attributo `part`).

## Vincoli applicativi/database

- `unique_part_number_per_workshop`: workshop, part_number

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]]
