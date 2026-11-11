---
title: "accounts_user"
tags:
  - rvkeeper
  - database-table
  - accounts
---

# `accounts_user`

**Modello Django:** `accounts.User`  
**Descrizione:** Utente  
**App:** `accounts`  
**Codice:** [accounts/models.py](../../../accounts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `password` | `password` | `CharField` | NOT NULL |
| `last_login` | `last_login` | `DateTimeField` | NULL, blank |
| `is_superuser` | `is_superuser` | `BooleanField` | NOT NULL |
| `first_name` | `first_name` | `CharField` | blank |
| `last_name` | `last_name` | `CharField` | blank |
| `is_staff` | `is_staff` | `BooleanField` | NOT NULL |
| `is_active` | `is_active` | `BooleanField` | NOT NULL |
| `date_joined` | `date_joined` | `DateTimeField` | NOT NULL |
| `username` | `username` | `CharField` | UNIQUE |
| `email` | `email` | `CharField` | NOT NULL |
| `preferred_language` | `preferred_language` | `CharField` | NOT NULL; valori: English, Italiano, Français, Deutsch, Español |
| `department` | `department` | `CharField` | NOT NULL; valori: Reception, Technician, Details, Parts, Warranty, Admin |
| `specialty` | `specialty` | `CharField` | blank; valori: Interior, Engine, Body, General, Detailing |
| `seniority` | `seniority` | `CharField` | NOT NULL; valori: Meccanico, Meccanico senior, Responsabile |

## Riferimenti in ingresso

- [[DB - workshops_membership]]. Campo `user_id` (attributo `user`).
- [[DB - fleet_partsrequest]]. Campo `requested_by_id` (attributo `requested_by`).
- [[DB - fleet_partsrequest]]. Campo `delivered_by_id` (attributo `delivered_by`).
- [[DB - fleet_warrantyclaim]]. Campo `requested_by_id` (attributo `requested_by`).
- [[DB - fleet_warrantyclaim]]. Campo `decided_by_id` (attributo `decided_by`).
- [[DB - fleet_warrantyreturn]]. Campo `decided_by_id` (attributo `decided_by`).
- [[DB - fleet_warrantyreturn]]. Campo `requested_by_id` (attributo `requested_by`).
- [[DB - fleet_jobnote]]. Campo `author_id` (attributo `author`).
- [[DB - fleet_attachment]]. Campo `uploaded_by_id` (attributo `uploaded_by`).
- [[DB - fleet_notification]]. Campo `user_id` (attributo `user`).
- [[DB - fleet_timeevent]]. Campo `mechanic_id` (attributo `mechanic`).
- [[DB - fleet_jobassignment]]. Campo `from_technician_id` (attributo `from_technician`).
- [[DB - fleet_jobassignment]]. Campo `to_technician_id` (attributo `to_technician`).
- [[DB - fleet_auditlog]]. Campo `actor_id` (attributo `actor`).
- [[DB - fleet_jobparticipation]]. Campo `mechanic_id` (attributo `mechanic`).
- [[DB - clientandsuppliers_contactdocument]]. Campo `uploaded_by_id` (attributo `uploaded_by`).
- [[DB - orders_workorder]]. Campo `invoiced_by_id` (attributo `invoiced_by`).
- [[DB - orders_workorder]]. Campo `created_by_id` (attributo `created_by`).
- [[DB - orders_jobcall]]. Campo `mechanic_id` (attributo `mechanic`).
- [[DB - orders_jobcall]]. Campo `called_by_id` (attributo `called_by`).
- [[DB - parts_partdocument]]. Campo `uploaded_by_id` (attributo `uploaded_by`).
- [[DB - parts_partmovement]]. Campo `created_by_id` (attributo `created_by`).
- [[DB - quotes_quote]]. Campo `created_by_id` (attributo `created_by`).

## Relazioni N:M

| Campo | Modello collegato | Tabella ponte |
|---|---|---|
| `groups` | `auth_group` (Django) | `accounts_user_groups` |
| `user_permissions` | `auth_permission` (Django) | `accounts_user_user_permissions` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: nessuna FK in uscita
