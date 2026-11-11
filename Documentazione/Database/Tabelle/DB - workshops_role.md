---
title: "workshops_role"
tags:
  - rvkeeper
  - database-table
  - workshops
---

# `workshops_role`

**Modello Django:** `workshops.Role`  
**Descrizione:** Ruolo  
**App:** `workshops`  
**Codice:** [workshops/models.py](../../../workshops/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `name` | `name` | `CharField` | NOT NULL |
| `code` | `code` | `SlugField` | NOT NULL |
| `description` | `description` | `TextField` | blank |
| `is_system` | `is_system` | `BooleanField` | NOT NULL |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |

## Riferimenti in ingresso

- [[DB - workshops_membership]]. Campo `role_id` (attributo `role`).

## Relazioni N:M

| Campo | Modello collegato | Tabella ponte |
|---|---|---|
| `permissions` | `auth_permission` (Django) | `workshops_role_permissions` |

## Vincoli applicativi/database

- `unique_role_code_per_workshop`: workshop, code

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]]
