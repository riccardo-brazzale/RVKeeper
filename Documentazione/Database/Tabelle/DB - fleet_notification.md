---
title: "fleet_notification"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_notification`

**Modello Django:** `fleet.Notification`  
**Descrizione:** notification  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `user_id` | `user` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `title` | `title` | `CharField` | NOT NULL |
| `body` | `body` | `TextField` | blank |
| `link` | `link` | `CharField` | blank |
| `work_order_id` | `work_order` | `ForeignKey` | NULL, blank -> [[DB - orders_workorder]] |
| `read` | `read` | `BooleanField` | NOT NULL |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `user` | [[DB - accounts_user]] | `CASCADE` |
| `work_order` | [[DB - orders_workorder]] | `CASCADE` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - accounts_user]], [[DB - orders_workorder]]
