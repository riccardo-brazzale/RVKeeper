---
title: "fleet_jobassignment"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_jobassignment`

**Modello Django:** `fleet.JobAssignment`  
**Descrizione:** job assignment  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `job_id` | `job` | `ForeignKey` | NOT NULL -> [[DB - orders_job]] |
| `from_technician_id` | `from_technician` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `to_technician_id` | `to_technician` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `reason` | `reason` | `CharField` | blank |
| `note` | `note` | `TextField` | blank |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `CASCADE` |
| `from_technician` | [[DB - accounts_user]] | `SET_NULL` |
| `to_technician` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_job]], [[DB - accounts_user]], [[DB - accounts_user]]
