---
title: "fleet_warrantyreturn"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_warrantyreturn`

**Modello Django:** `fleet.WarrantyReturn`  
**Descrizione:** warranty return  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `work_order_id` | `work_order` | `ForeignKey` | NOT NULL -> [[DB - orders_workorder]] |
| `job_id` | `job` | `ForeignKey` | NULL, blank -> [[DB - orders_job]] |
| `parts_request_id` | `parts_request` | `ForeignKey` | NULL, blank -> [[DB - fleet_partsrequest]] |
| `part_name` | `part_name` | `CharField` | NOT NULL |
| `part_number` | `part_number` | `CharField` | blank |
| `quantity` | `quantity` | `DecimalField` | NOT NULL |
| `received_date` | `received_date` | `DateField` | NULL, blank |
| `defect_description` | `defect_description` | `TextField` | blank |
| `serial_number` | `serial_number` | `CharField` | blank |
| `reason` | `reason` | `CharField` | blank |
| `notes` | `notes` | `TextField` | blank |
| `photos` | `photos` | `JSONField` | blank |
| `status` | `status` | `CharField` | NOT NULL; valori: Submitted, In Review, Return Approved, Replacement Approved, Credit Approved, Declined |
| `decision_notes` | `decision_notes` | `TextField` | blank |
| `decided_by_id` | `decided_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `decided_at` | `decided_at` | `DateTimeField` | NULL, blank |
| `requested_by_id` | `requested_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `work_order` | [[DB - orders_workorder]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `SET_NULL` |
| `parts_request` | [[DB - fleet_partsrequest]] | `SET_NULL` |
| `decided_by` | [[DB - accounts_user]] | `SET_NULL` |
| `requested_by` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_workorder]], [[DB - orders_job]], [[DB - fleet_partsrequest]], [[DB - accounts_user]], [[DB - accounts_user]]
