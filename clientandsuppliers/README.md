# Clienti e fornitori

Questa app possiede le proprie tabelle `clientandsuppliers_*` per le anagrafiche commerciali e i documenti allegati. Una singola anagrafica può essere cliente, fornitore o entrambi e può avere più documenti classificati tramite `fleet.DocumentCategory`.

Gli allegati sono archiviati sotto `MEDIA_ROOT/contacts/<nome-o-ragione-sociale>/<categoria>/` e consultabili dalla scheda del contatto.
