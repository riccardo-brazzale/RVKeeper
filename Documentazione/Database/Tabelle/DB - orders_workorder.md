---
title: "orders_workorder"
tags:
  - rvkeeper
  - database-table
  - orders
---

# `orders_workorder`

**Modello Django:** `orders.WorkOrder`  
**Descrizione:** work order  
**App:** `orders`  
**Codice:** [orders/models.py](../../../orders/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK, UNIQUE, blank |
| `workshop_id` | `workshop` | `ForeignKey` | NOT NULL -> [[DB - workshops_workshop]] |
| `customer_id` | `customer` | `ForeignKey` | NULL, blank -> [[DB - clientandsuppliers_camperowner]] |
| `vehicle_id` | `vehicle` | `ForeignKey` | NULL, blank -> [[DB - fleet_camper]] |
| `ro_number` | `ro_number` | `CharField` | NOT NULL |
| `year` | `year` | `CharField` | blank |
| `make` | `make` | `CharField` | blank |
| `model` | `model` | `CharField` | blank |
| `customer_name` | `customer_name` | `CharField` | blank |
| `customer_phone` | `customer_phone` | `CharField` | blank |
| `customer_email` | `customer_email` | `CharField` | blank |
| `odometer` | `odometer` | `PositiveIntegerField` | NULL, blank |
| `work_classification` | `work_classification` | `CharField` | NOT NULL; valori: A pagamento, Stock |
| `warranty_status` | `warranty_status` | `CharField` | NOT NULL; valori: Not Applicable, Pending, Approved, Partially Approved, Declined |
| `status` | `status` | `CharField` | NOT NULL; valori: Aperto, In lavorazione, In attesa di collaudo, Pronto alla consegna, Lavori aggiuntivi, Chiuso, Annullato |
| `completed_at` | `completed_at` | `DateTimeField` | NULL, blank |
| `invoiced` | `invoiced` | `BooleanField` | NOT NULL |
| `invoiced_at` | `invoiced_at` | `DateTimeField` | NULL, blank |
| `invoiced_by_id` | `invoiced_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `reception_notes` | `reception_notes` | `TextField` | blank |
| `checklist` | `checklist` | `JSONField` | blank |
| `damages` | `damages` | `JSONField` | blank |
| `created_by_id` | `created_by` | `ForeignKey` | NULL, blank -> [[DB - accounts_user]] |
| `created_at` | `created_at` | `DateTimeField` | blank |
| `updated_at` | `updated_at` | `DateTimeField` | blank |

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `workshop` | [[DB - workshops_workshop]] | `CASCADE` |
| `customer` | [[DB - clientandsuppliers_camperowner]] | `PROTECT` |
| `vehicle` | [[DB - fleet_camper]] | `SET_NULL` |
| `invoiced_by` | [[DB - accounts_user]] | `SET_NULL` |
| `created_by` | [[DB - accounts_user]] | `SET_NULL` |

## Riferimenti in ingresso

- [[DB - fleet_partsrequest]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - fleet_warrantyclaim]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - fleet_warrantyreturn]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - fleet_attachment]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - fleet_notification]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - fleet_auditlog]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - orders_job]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - parts_partmovement]]. Campo `work_order_id` (attributo `work_order`).
- [[DB - quotes_quote]]. Campo `work_order_id` (attributo `work_order`).

## Vincoli applicativi/database

- `unique_ro_per_workshop`: workshop, ro_number

## Navigazione

- [[Database PostgreSQL RVKeeper]]
- Tabelle collegate: [[DB - workshops_workshop]], [[DB - clientandsuppliers_camperowner]], [[DB - fleet_camper]], [[DB - accounts_user]], [[DB - accounts_user]]
