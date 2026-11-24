---
title: "orders_documentcategory"
tags:
  - rvkeeper
  - database-table
  - orders
---

# `orders_documentcategory`

**Modello Django:** `orders.DocumentCategory`  
**Descrizione:** Categoria documento  
**App:** `orders`  
**Codice:** [orders/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `code` | `code` | `SlugField` | UNIQUE |
| `name` | `name` | `CharField` | UNIQUE |
| `description` | `description` | `CharField` | blank |
| `is_active` | `is_active` | `BooleanField` | NOT NULL |
| `sort_order` | `sort_order` | `PositiveSmallIntegerField` | NOT NULL |

## Riferimenti in ingresso

- [[DB - fleet_camperphoto]]. Campo `category_id` (attributo `category`).
- [[DB - orders_attachment]]. Campo `category_id` (attributo `category`).
- [[DB - clientandsuppliers_contactdocument]]. Campo `category_id` (attributo `category`).
- [[DB - parts_partdocument]]. Campo `category_id` (attributo `category`).

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: nessuna FK in uscita
