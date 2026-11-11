---
title: "fleet_partsrequest"
tags:
  - rvkeeper
  - database-table
  - fleet
---

# `fleet_partsrequest`

**Modello Django:** `fleet.PartsRequest`  
**Descrizione:** parts request  
**App:** `fleet`  
**Codice:** [fleet/models.py](../../../fleet/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `work_order_id` | `work_order` | `ForeignKey` | NOT NULL -> [[DB - orders_workorder]] |
| `job_id` | `job` | `ForeignKey` | NULL, blank -> [[DB - orders_job]] |
| `part_id` | `part` | `ForeignKey` | NULL, blank -> [[DB - parts_part]] |
| `supplier_offer_id` | `supplier_offer` | `ForeignKey` | NULL, blank -> [[DB - parts_partsupplieroffer]] |
| `custom_item` | `custom_item` | `CharField` | blank |
| `unit` | `unit` | `CharField` | NOT NULL |
| `quantity_requested` | `quantity_requested` | `DecimalField` | NOT NULL |
| `unit_delivered` | `unit_delivered` | `CharField` | blank |
| `quantity_delivered` | `quantity_delivered` | `DecimalField` | NOT NULL |
| `conversion_factor` | `conversion_factor` | `DecimalField` | NOT NULL |
| `repair_minutes` | `repair_minutes` | `PositiveIntegerField` | NOT NULL |
| `notes` | `notes` | `TextField` | blank |
| `supplier` | `supplier` | `CharField` | blank |
| `purchase_price` | `purchase_price` | `DecimalField` | NULL, blank |
| `order_number` | `order_number` | `CharField` | blank |
| `status` | `status` | `CharField` | NOT NULL; valori: New, Pending, Preparing, Ready For Pickup, Delivered, Cancelled |
| `warranty_claim_id` | `warranty_claim` | `ForeignKey` | NULL, blank -> [[DB - fleet_warrantyclaim]] |
| `authorization` | `authorization` | `TextField` | blank |
| `documents` | `documents` | `JSONField` | blank |
| `defect_photos` | `defect_photos` | `JSONField` | blank |
| `defect_description` | `defect_description` | `TextField` | blank |
| `requested_by_id` | `requested_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `delivered_at` | `delivered_at` | `DateTimeField` | NULL, blank |
| `delivered_by_id` | `delivered_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `inventory_applied` | `inventory_applied` | `BooleanField` | NOT NULL |
| `created_at` | `created_at` | `DateTimeField` | blank |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `work_order` | [[DB - orders_workorder]] | `CASCADE` |
| `job` | [[DB - orders_job]] | `SET_NULL` |
| `part` | [[DB - parts_part]] | `SET_NULL` |
| `supplier_offer` | [[DB - parts_partsupplieroffer]] | `SET_NULL` |
| `warranty_claim` | [[DB - fleet_warrantyclaim]] | `SET_NULL` |
| `requested_by` | [[DB - accounts_user]] | `SET_NULL` |
| `delivered_by` | [[DB - accounts_user]] | `SET_NULL` |

## Riferimenti in ingresso

- [[DB - fleet_warrantyreturn]]. Campo `parts_request_id` (attributo `parts_request`).

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - orders_workorder]], [[DB - orders_job]], [[DB - parts_part]], [[DB - parts_partsupplieroffer]], [[DB - fleet_warrantyclaim]], [[DB - accounts_user]], [[DB - accounts_user]]
