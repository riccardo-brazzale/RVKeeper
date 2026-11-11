---
title: "clientandsuppliers_camperowner"
tags:
  - rvkeeper
  - database-table
  - clientandsuppliers
---

# `clientandsuppliers_camperowner`

**Modello Django:** `clientandsuppliers.CamperOwner`  
**Descrizione:** Contatto commerciale  
**App:** `clientandsuppliers`  
**Codice:** [clientandsuppliers/models.py](../../../clientandsuppliers/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `kind` | `kind` | `CharField` | NOT NULL; valori: Cliente, Fornitore, Cliente e fornitore |
| `is_company` | `is_company` | `BooleanField` | NOT NULL |
| `first_name` | `first_name` | `CharField` | blank |
| `last_name` | `last_name` | `CharField` | blank |
| `company_name` | `company_name` | `CharField` | blank |
| `tax_code` | `tax_code` | `CharField` | blank |
| `vat_number` | `vat_number` | `CharField` | blank |
| `phone` | `phone` | `CharField` | blank |
| `email` | `email` | `CharField` | blank |
| `address` | `address` | `CharField` | blank |
| `postal_code` | `postal_code` | `CharField` | blank |
| `city` | `city` | `CharField` | blank |
| `country` | `country` | `CharField` | NOT NULL |
| `notes` | `notes` | `TextField` | blank |
| `created_at` | `created_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |

## Riferimenti in ingresso

- [[DB - fleet_camper]]. Campo `owner_id` (attributo `owner`).
- [[DB - clientandsuppliers_contactdocument]]. Campo `contact_id` (attributo `contact`).
- [[DB - orders_workorder]]. Campo `customer_id` (attributo `customer`).
- [[DB - parts_partsupplieroffer]]. Campo `supplier_id` (attributo `supplier`).
- [[DB - quotes_quote]]. Campo `customer_id` (attributo `customer`).

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]]
