---
title: "fleet_jobparticipation"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_jobparticipation`

**Modello Django:** `fleet.JobParticipation`  
**Descrizione:** job participation  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `job_id` | `job` | `ForeignKey` | NOT NULL -> [[DB - orders_job]] |
| `mechanic_id` | `mechanic` | `ForeignKey` | NOT NULL -> [[DB - accounts_user]] |
| `source` | `source` | `CharField` | NOT NULL; valori: Chiamata/assegnazione, Iniziativa propria |
| `is_active` | `is_active` | `BooleanField` | NOT NULL |
| `started_at` | `started_at` | `DateTimeField` | NULL, blank |
| `paused_at` | `paused_at` | `DateTimeField` | NULL, blank |
| `finished_at` | `finished_at` | `DateTimeField` | NULL, blank |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `CASCADE` |
| `mechanic` | [[DB - accounts_user]] | `CASCADE` |

## Vincoli applicativi/database

- `unique_active_job_mechanic`: job, mechanic

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_job]], [[DB - accounts_user]]
