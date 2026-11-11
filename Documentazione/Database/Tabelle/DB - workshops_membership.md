---
title: "workshops_membership"
tags:
  - rvkeeper
  - database-table
  - workshops
---

# `workshops_membership`

**Modello Django:** `workshops.Membership`  
**Descrizione:** Appartenenza  
**App:** `workshops`  
**Codice:** [workshops/models.py](../../../workshops/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `user_id` | `user` | `ForeignKey` | NOT NULL -> [[DB - accounts_user]] |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `role_id` | `role` | `ForeignKey` | NOT NULL -> [[DB - workshops_role]] |
| `is_active` | `is_active` | `BooleanField` | NOT NULL |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `user` | [[DB - accounts_user]] | `CASCADE` |
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `role` | [[DB - workshops_role]] | `PROTECT` |

## Vincoli applicativi/database

- `unique_user_per_workshop`: user, workshop

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - accounts_user]], [[DB - workshops_workshop]], [[DB - workshops_role]]
