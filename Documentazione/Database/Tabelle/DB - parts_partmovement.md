---
title: "parts_partmovement"
tags:
  - rvkeeper
  - database-table
  - parts
---

# `parts_partmovement`

**Modello Django:** `parts.PartMovement`  
**Descrizione:** part movement  
**App:** `parts`  
**Codice:** [parts/models.py](../../../parts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `part_id` | `part` | `ForeignKey` | NOT NULL -> [[DB - parts_part]] |
| `work_order_id` | `work_order` | `ForeignKey` | NULL, blank -> [[DB - orders_workorder]] |
| `movement_type` | `movement_type` | `CharField` | NOT NULL; valori: Carico, Scarico, Rettifica |
| `quantity` | `quantity` | `DecimalField` | NOT NULL |
| `unit_cost` | `unit_cost` | `DecimalField` | NOT NULL |
| `note` | `note` | `CharField` | blank |
| `created_by_id` | `created_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `part` | [[DB - parts_part]] | `PROTECT` |
| `work_order` | [[DB - orders_workorder]] | `SET_NULL` |
| `created_by` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - parts_part]], [[DB - orders_workorder]], [[DB - accounts_user]]
