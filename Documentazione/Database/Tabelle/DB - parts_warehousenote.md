---
title: "parts_warehousenote"
tags:
  - rvkeeper
  - database-table
  - parts
---

# `parts_warehousenote`

**Modello Django:** `parts.WarehouseNote`  
**Descrizione:** Comunicazione del magazzino su disponibilita e consegna  
**App:** `parts`  
**Codice:** [parts/models.py](../../../parts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `work_order_id` | `work_order` | `ForeignKey` | NOT NULL -> [[DB - orders_workorder]] |
| `parts_request_id` | `parts_request` | `ForeignKey` | NULL, blank -> [[DB - parts_partsrequest]] |
| `part_id` | `part` | `ForeignKey` | NULL, blank -> [[DB - parts_part]] |
| `author_id` | `author` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `text` | `text` | `TextField` | NOT NULL |
| `estimated_delivery_at` | `estimated_delivery_at` | `DateField` | NULL, blank |
| `created_at` | `created_at` | `DateTimeField` | NOT NULL |

## Indici

- `warehouse_note_order_idx`: `workshop_id`, `work_order_id`, `created_at`.

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `work_order` | [[DB - orders_workorder]] | `CASCADE` |
| `parts_request` | [[DB - parts_partsrequest]] | `CASCADE` |
| `part` | [[DB - parts_part]] | `SET_NULL` |
| `author` | [[DB - accounts_user]] | `SET_NULL` |

## Riferimenti in ingresso

- `parts_warehousenoteread`: ricevute di lettura collegate alla nota.
