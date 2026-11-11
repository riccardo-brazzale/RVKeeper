---
title: "fleet_jobnote"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_jobnote`

**Modello Django:** `fleet.JobNote`  
**Descrizione:** job note  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `job_id` | `job` | `ForeignKey` | NOT NULL -> [[DB - orders_job]] |
| `author_id` | `author` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `department` | `department` | `CharField` | blank |
| `text` | `text` | `TextField` | NOT NULL |
| `language` | `language` | `CharField` | NOT NULL |
| `translations` | `translations` | `JSONField` | blank |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `CASCADE` |
| `author` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_job]], [[DB - accounts_user]]
