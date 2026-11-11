---
title: "quotes_quoteline"
tags:
  - rvkeeper
  - database-table
  - quotes
---

# `quotes_quoteline`

**Modello Django:** `quotes.QuoteLine`  
**Descrizione:** quote line  
**App:** `quotes`  
**Codice:** [quotes/models.py](../../../quotes/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `quote_id` | `quote` | `ForeignKey` | NOT NULL -> [[DB - quotes_quote]] |
| `line_type` | `line_type` | `CharField` | NOT NULL; valori: Ricambio, Manodopera, Altro |
| `part_id` | `part` | `ForeignKey` | NULL, blank -> [[DB - parts_part]] |
| `description` | `description` | `CharField` | NOT NULL |
| `quantity` | `quantity` | `DecimalField` | NOT NULL |
| `unit` | `unit` | `CharField` | NOT NULL |
| `unit_price` | `unit_price` | `DecimalField` | NOT NULL |
| `discount_percent` | `discount_percent` | `DecimalField` | NOT NULL |
| `standard_minutes` | `standard_minutes` | `PositiveIntegerField` | NOT NULL |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `quote` | [[DB - quotes_quote]] | `CASCADE` |
| `part` | [[DB - parts_part]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - quotes_quote]], [[DB - parts_part]]
