---
title: "orders_job"
tags:
  - rvkeeper
  - database-table
  - orders
---

# `orders_job`

**Modello Django:** `orders.Job`  
**Descrizione:** job  
**App:** `orders`  
**Codice:** [orders/models.py](../../../orders/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `work_order_id` | `work_order` | `ForeignKey` | NOT NULL -> [[DB - orders_workorder]] |
| `job_number` | `job_number` | `PositiveIntegerField` | NOT NULL |
| `title` | `title` | `CharField` | NOT NULL |
| `labor_article_id` | `labor_article` | `ForeignKey` | NULL, blank -> `orders_laborarticle` |
| `description` | `description` | `TextField` | blank |
| `category` | `category` | `CharField` | NOT NULL; valori: Customer Pay, Warranty, Stock |
| `department` | `department` | `CharField` | NOT NULL; valori: Technician, Details |
| `specialty` | `specialty` | `CharField` | NOT NULL; valori: Interior, Engine, Body, General, Detailing |
| `status` | `status` | `CharField` | NOT NULL; valori: Not Started, In Progress, Paused, Waiting Parts, Waiting Warranty, Completed, Cancelled |
| `invoice_hourly_rate_override` | `invoice_hourly_rate_override` | `DecimalField` | NULL, blank; tariffa oraria personalizzata per la riga di fatturazione |
| `reception_notes` | `reception_notes` | `TextField` | blank |
| `standard_minutes` | `standard_minutes` | `PositiveIntegerField` | NOT NULL |
| `block_reason` | `block_reason` | `TextField` | blank |
| `started_at` | `started_at` | `DateTimeField` | NULL, blank |
| `completed_at` | `completed_at` | `DateTimeField` | NULL, blank |
| `warranty_decision` | `warranty_decision` | `CharField` | blank |
| `warranty_hours` | `warranty_hours` | `DecimalField` | NULL, blank |
| `warranty_reason` | `warranty_reason` | `TextField` | blank |
| `parts_ready` | `parts_ready` | `BooleanField` | NOT NULL |
| `created_at` | `created_at` | `DateTimeField` | blank |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `work_order` | [[DB - orders_workorder]] | `CASCADE` |
| `labor_article` | `orders_laborarticle` | `PROTECT` |

## Riferimenti in ingresso

- [[DB - parts_partsrequest]]. Campo `job_id` (attributo `job`).
- [[DB - orders_warrantyclaim]]. Campo `job_id` (attributo `job`).
- [[DB - orders_warrantyreturn]]. Campo `job_id` (attributo `job`).
- [[DB - orders_jobnote]]. Campo `job_id` (attributo `job`).
- [[DB - orders_attachment]]. Campo `job_id` (attributo `job`).
- [[DB - orders_timeevent]]. Campo `job_id` (attributo `job`).
- [[DB - orders_jobassignment]]. Campo `job_id` (attributo `job`).
- [[DB - orders_jobparticipation]]. Campo `job_id` (attributo `job`).
- [[DB - orders_jobcall]]. Campo `job_id` (attributo `job`).

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_workorder]]
