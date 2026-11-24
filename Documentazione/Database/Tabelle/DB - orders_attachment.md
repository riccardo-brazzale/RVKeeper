---
title: "orders_attachment"
tags:
  - rvkeeper
  - database-table
  - orders
---

# `orders_attachment`

**Modello Django:** `orders.Attachment`  
**Descrizione:** attachment  
**App:** `orders`  
**Codice:** [orders/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `work_order_id` | `work_order` | `ForeignKey` | NULL, blank -> [[DB - orders_workorder]] |
| `job_id` | `job` | `ForeignKey` | NULL, blank -> [[DB - orders_job]] |
| `category_id` | `category` | `ForeignKey` | NOT NULL -> [[DB - orders_documentcategory]] |
| `file` | `file` | `FileField` | NOT NULL |
| `file_name` | `file_name` | `CharField` | NOT NULL |
| `caption` | `caption` | `CharField` | blank |
| `uploaded_by_id` | `uploaded_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `department` | `department` | `CharField` | blank |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `work_order` | [[DB - orders_workorder]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `CASCADE` |
| `category` | [[DB - orders_documentcategory]] | `PROTECT` |
| `uploaded_by` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_workorder]], [[DB - orders_job]], [[DB - orders_documentcategory]], [[DB - accounts_user]]
