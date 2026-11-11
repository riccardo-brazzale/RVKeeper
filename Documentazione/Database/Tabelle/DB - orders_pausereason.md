---
title: "orders_pausereason"
tags:
  - rvkeeper
  - database-table
  - orders
---

# `orders_pausereason`

**Modello Django:** `orders.PauseReason`  
**Descrizione:** Causale pausa  
**App:** `orders`  
**Codice:** [orders/models.py](../../../orders/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `code` | `code` | `SlugField` | UNIQUE |
| `label` | `label` | `CharField` | UNIQUE |
| `is_active` | `is_active` | `BooleanField` | NOT NULL |
| `sort_order` | `sort_order` | `PositiveSmallIntegerField` | NOT NULL |

## Riferimenti in ingresso

- [[DB - fleet_timeevent]]. Campo `pause_reason_id` (attributo `pause_reason`).

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: nessuna FK in uscita
