---
title: "orders_jobcall"
tags:
  - rvkeeper
  - database-table
  - orders
---

# `orders_jobcall`

**Modello Django:** `orders.JobCall`  
**Descrizione:** job call  
**App:** `orders`  
**Codice:** [orders/models.py](../../../orders/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `job_id` | `job` | `ForeignKey` | NOT NULL -> [[DB - orders_job]] |
| `mechanic_id` | `mechanic` | `ForeignKey` | NOT NULL -> [[DB - accounts_user]] |
| `called_by_id` | `called_by` | `ForeignKey` | NULL -> [[DB - accounts_user]] |
| `accepted_at` | `accepted_at` | `DateTimeField` | NULL, blank |
| `dismissed_at` | `dismissed_at` | `DateTimeField` | NULL, blank |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `CASCADE` |
| `mechanic` | [[DB - accounts_user]] | `CASCADE` |
| `called_by` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_job]], [[DB - accounts_user]], [[DB - accounts_user]]
