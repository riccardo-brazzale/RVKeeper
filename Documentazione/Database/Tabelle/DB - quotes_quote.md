---
title: "quotes_quote"
tags:
  - rvkeeper
  - database-table
  - quotes
---

# `quotes_quote`

**Modello Django:** `quotes.Quote`  
**Descrizione:** Preventivo  
**App:** `quotes`  
**Codice:** [quotes/models.py](../../../quotes/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `quote_number` | `quote_number` | `CharField` | NOT NULL |
| `customer_id` | `customer` | `ForeignKey` | NOT NULL -> [[DB - clientandsuppliers_camperowner]] |
| `vehicle_id` | `vehicle` | `ForeignKey` | NULL, blank -> [[DB - fleet_camper]] |
| `work_order_id` | `work_order` | `OneToOneField` | NULL, UNIQUE, blank -> [[DB - orders_workorder]] |
| `status` | `status` | `CharField` | NOT NULL; valori: Bozza, Inviato, Accettato, Rifiutato, Scaduto |
| `description` | `description` | `TextField` | blank |
| `notes` | `notes` | `TextField` | blank |
| `valid_until` | `valid_until` | `DateField` | NULL, blank |
| `created_by_id` | `created_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `created_at` | `created_at` | `DateTimeField` | blank |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `customer` | [[DB - clientandsuppliers_camperowner]] | `PROTECT` |
| `vehicle` | [[DB - fleet_camper]] | `SET_NULL` |
| `work_order` | [[DB - orders_workorder]] | `SET_NULL` |
| `created_by` | [[DB - accounts_user]] | `SET_NULL` |

## Riferimenti in ingresso

- [[DB - quotes_quoteline]]. Campo `quote_id` (attributo `quote`).

## Vincoli applicativi/database

- `unique_quote_number_per_workshop`: workshop, quote_number

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - clientandsuppliers_camperowner]], [[DB - fleet_camper]], [[DB - orders_workorder]], [[DB - accounts_user]]
