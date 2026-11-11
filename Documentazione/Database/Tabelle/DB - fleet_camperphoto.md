---
title: "fleet_camperphoto"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_camperphoto`

**Modello Django:** `fleet.CamperPhoto`  
**Descrizione:** Fotografia  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `camper_id` | `camper` | `ForeignKey` | NOT NULL -> [[DB - fleet_camper]] |
| `image` | `image` | `FileField` | NOT NULL |
| `category_id` | `category` | `ForeignKey` | NOT NULL -> [[DB - fleet_documentcategory]] |
| `caption` | `caption` | `CharField` | blank |
| `uploaded_at` | `uploaded_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `camper` | [[DB - fleet_camper]] | `CASCADE` |
| `category` | [[DB - fleet_documentcategory]] | `PROTECT` |

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - fleet_camper]], [[DB - fleet_documentcategory]]
