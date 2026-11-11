# Ricambi e magazzino

Questa app possiede il proprio schema (`parts_*`): articoli, offerte fornitore, documenti classificati e movimenti di magazzino. Le categorie documento sono configurate dall'admin tramite `fleet.DocumentCategory`; ogni articolo può avere più foto, manuali e schede tecniche. I file sono archiviati sotto `MEDIA_ROOT/parts/<codice>/<categoria>/`.

Le viste filtrano per officina e registrano le variazioni stock come movimenti collegabili a un ordine di lavoro.
