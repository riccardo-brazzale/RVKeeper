---
title: "parts_partdocument"
tags:
  - rvkeeper
  - database-table
  - parts
---

# `parts_partdocument`

**Modello Django:** `parts.PartDocument`  
**Descrizione:** part document  
**App:** `parts`  
**Codice:** [parts/models.py](../../../parts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `part_id` | `part` | `ForeignKey` | NOT NULL -> [[DB - parts_part]] |
| `category_id` | `category` | `ForeignKey` | NOT NULL -> [[DB - fleet_documentcategory]] |
| `file` | `file` | `FileField` | NOT NULL |
| `caption` | `caption` | `CharField` | blank |
| `uploaded_by_id` | `uploaded_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `part` | [[DB - parts_part]] | `CASCADE` |
| `category` | [[DB - fleet_documentcategory]] | `PROTECT` |
| `uploaded_by` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - parts_part]], [[DB - fleet_documentcategory]], [[DB - accounts_user]]
