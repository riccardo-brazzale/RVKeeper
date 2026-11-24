---
title: "parts_warehousenoteread"
tags:
  - rvkeeper
  - database-table
  - parts
---

# `parts_warehousenoteread`

**Modello Django:** `parts.WarehouseNoteRead`  
**Descrizione:** Stato di lettura della nota per destinatario  
**App:** `parts`  
**Codice:** [parts/models.py](../../../parts/models.py)

## Colonne

| Colonna SQL | Campo Django | Tipo | Vincoli / relazione |
|---|---|---|---|
| `id` | `id` | `BigAutoField` | PK |
| `note_id` | `note` | `ForeignKey` | NOT NULL -> [[DB - parts_warehousenote]] |
| `recipient_id` | `recipient` | `ForeignKey` | NOT NULL -> [[DB - accounts_user]] |
| `read_at` | `read_at` | `DateTimeField` | NULL, blank |

## Vincoli e indici

- `unique_warehouse_note_recipient`: una ricevuta per nota e destinatario.
- `warehouse_note_unread_idx`: indice su `recipient_id`, `read_at`.

## Riferimenti in uscita (FK)

| Campo | Tabella collegata | ON DELETE |
|---|---|---|
| `note` | [[DB - parts_warehousenote]] | `CASCADE` |
| `recipient` | [[DB - accounts_user]] | `CASCADE` |
