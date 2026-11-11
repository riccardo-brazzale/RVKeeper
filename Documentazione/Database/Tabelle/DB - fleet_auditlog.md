---
title: "fleet_auditlog"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_auditlog`

**Modello Django:** `fleet.AuditLog`  
**Descrizione:** audit log  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `actor_id` | `actor` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `action` | `action` | `CharField` | NOT NULL |
| `entity_type` | `entity_type` | `CharField` | NOT NULL |
| `entity_id` | `entity_id` | `CharField` | blank |
| `work_order_id` | `work_order` | `ForeignKey` | NULL, blank -> [[DB - orders_workorder]] |
| `details` | `details` | `TextField` | blank |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `actor` | [[DB - accounts_user]] | `SET_NULL` |
| `work_order` | [[DB - orders_workorder]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - accounts_user]], [[DB - orders_workorder]]
