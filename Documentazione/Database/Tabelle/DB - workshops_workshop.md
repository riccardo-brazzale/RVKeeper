---
title: "workshops_workshop"
tags:
  - rvkeeper
  - database-table
  - workshops
---

# `workshops_workshop`

**Modello Django:** `workshops.Workshop`  
**Descrizione:** Officina  
**App:** `workshops`  
**Codice:** [workshops/models.py](../../../workshops/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `name` | `name` | `CharField` | NOT NULL |
| `slug` | `slug` | `SlugField` | UNIQUE |
| `country` | `country` | `CharField` | NOT NULL |
| `default_language` | `default_language` | `CharField` | NOT NULL; valori: English, Italiano |
| `timezone` | `timezone` | `CharField` | NOT NULL |
| `currency` | `currency` | `CharField` | NOT NULL |
| `is_active` | `is_active` | `BooleanField` | NOT NULL |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in ingresso

- [[DB - workshops_role]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - workshops_membership]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_camper]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_partsrequest]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_warrantyclaim]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_warrantyreturn]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_jobnote]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_attachment]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_notification]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_timeevent]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_jobassignment]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_auditlog]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - fleet_jobparticipation]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - clientandsuppliers_camperowner]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - orders_workorder]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - orders_job]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - orders_jobcall]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - parts_part]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - parts_partmovement]]. Campo `workshop_id` (attributo `workshop`).
- [[DB - quotes_quote]]. Campo `workshop_id` (attributo `workshop`).

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: nessuna FK in uscita
