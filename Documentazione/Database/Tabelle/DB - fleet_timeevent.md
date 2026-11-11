---
title: "fleet_timeevent"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_timeevent`

**Modello Django:** `fleet.TimeEvent`  
**Descrizione:** time event  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `job_id` | `job` | `ForeignKey` | NOT NULL -> [[DB - orders_job]] |
| `mechanic_id` | `mechanic` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `event_type` | `event_type` | `CharField` | NOT NULL; valori: Start, Pause, Resume, Finish, Waiting, Reopen |
| `pause_reason_id` | `pause_reason` | `ForeignKey` | NULL, blank -> [[DB - orders_pausereason]] |
| `event_at` | `event_at` | `DateTimeField` | NOT NULL |
| `note` | `note` | `TextField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `CASCADE` |
| `mechanic` | [[DB - accounts_user]] | `SET_NULL` |
| `pause_reason` | [[DB - orders_pausereason]] | `PROTECT` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_job]], [[DB - accounts_user]], [[DB - orders_pausereason]]
