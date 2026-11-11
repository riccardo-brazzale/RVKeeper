---
title: "fleet_warrantyclaim"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_warrantyclaim`

**Modello Django:** `fleet.WarrantyClaim`  
**Descrizione:** warranty claim  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `work_order_id` | `work_order` | `ForeignKey` | NOT NULL -> [[DB - orders_workorder]] |
| `job_id` | `job` | `ForeignKey` | NULL, blank -> [[DB - orders_job]] |
| `component` | `component` | `CharField` | blank |
| `problem_description` | `problem_description` | `TextField` | NOT NULL |
| `work_needed` | `work_needed` | `TextField` | blank |
| `requested_hours` | `requested_hours` | `DecimalField` | NOT NULL |
| `approved_hours` | `approved_hours` | `DecimalField` | NULL, blank |
| `status` | `status` | `CharField` | NOT NULL; valori: Submitted, In Review, Approved, Partially Approved, Declined |
| `decision_notes` | `decision_notes` | `TextField` | blank |
| `photos` | `photos` | `JSONField` | blank |
| `requested_by_id` | `requested_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `decided_by_id` | `decided_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `decided_at` | `decided_at` | `DateTimeField` | NULL, blank |
| `created_at` | `created_at` | `DateTimeField` | blank |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `work_order` | [[DB - orders_workorder]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `SET_NULL` |
| `requested_by` | [[DB - accounts_user]] | `SET_NULL` |
| `decided_by` | [[DB - accounts_user]] | `SET_NULL` |

## Riferimenti in ingresso

- [[DB - fleet_partsrequest]]. Campo `warranty_claim_id` (attributo `warranty_claim`).

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_workorder]], [[DB - orders_job]], [[DB - accounts_user]], [[DB - accounts_user]]
