---
title: "clientandsuppliers_contactdocument"
tags:
  - rvkeeper
  - database-table
  - clientandsuppliers
---

# `clientandsuppliers_contactdocument`

**Modello Django:** `clientandsuppliers.ContactDocument`  
**Descrizione:** contact document  
**App:** `clientandsuppliers`  
**Codice:** [clientandsuppliers/models.py](../../../clientandsuppliers/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `contact_id` | `contact` | `ForeignKey` | NOT NULL -> [[DB - clientandsuppliers_camperowner]] |
| `category_id` | `category` | `ForeignKey` | NOT NULL -> [[DB - fleet_documentcategory]] |
| `file` | `file` | `FileField` | NOT NULL |
| `caption` | `caption` | `CharField` | blank |
| `uploaded_by_id` | `uploaded_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `contact` | [[DB - clientandsuppliers_camperowner]] | `CASCADE` |
| `category` | [[DB - fleet_documentcategory]] | `PROTECT` |
| `uploaded_by` | [[DB - accounts_user]] | `SET_NULL` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - clientandsuppliers_camperowner]], [[DB - fleet_documentcategory]], [[DB - accounts_user]]
