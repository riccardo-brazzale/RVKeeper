# Ricambi e magazzino

Questa app possiede il proprio schema (`parts_*`): articoli, offerte fornitore, richieste ricambi, consumi delle lavorazioni, note del magazzino, bolle, ordini e movimenti. Le categorie documento sono configurate dall'admin tramite `orders.DocumentCategory`; ogni articolo può avere più foto, manuali e schede tecniche. I file sono archiviati sotto `MEDIA_ROOT/parts/<codice>/<categoria>/`.

Le viste filtrano per officina e registrano le variazioni stock come movimenti collegabili a un ordine di lavoro. Le quantità impegnate per gli ordini sono rappresentate dalle righe della bolla di trasferimento: non riducono la giacenza fisica fino alla chiusura dell'ordine di lavoro; l'annullamento dell'ordine rilascia gli impegni.

Il magazzino gestisce gli ordini ai fornitori dalla sezione **Ordini fornitori**. Gli amministratori, i profili magazziniere e gli utenti o gruppi con il permesso Django `parts.manage_supplier_purchasing` possono gestire gli acquisti. Le richieste non coperte dallo stock vengono raggruppate per fornitore, usando l'offerta preferita o, in sua assenza, quella con il prezzo netto più basso. Quantità minima e multiplo di confezione determinano l'arrotondamento sempre per eccesso. La ricezione può essere parziale; ogni entrata aggiorna stock e impegni in attesa, mentre l'ordine può essere saldato anche con quantità residue.

Le richieste e i relativi modelli di magazzino sono di proprietà dell'app `parts`; i modelli operativi di officina (inclusi garanzie, notifiche e tempi) appartengono a `orders`.

I listini fornitore sono locali all'officina, validi per intervallo di date e importabili da CSV o XLSX. Le colonne richieste sono `codice_articolo_fornitore` e `prezzo`; `codice_interno` e `sconto` sono facoltative. La ricerca del catalogo include i codici articolo dei fornitori.
