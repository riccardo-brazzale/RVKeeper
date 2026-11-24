# Ordini e lavorazioni

Questa app possiede le tabelle `orders_*` per ordini di lavoro, lavorazioni, chiamate ai meccanici, causali pausa e processi operativi collegati. Comprende anche categorie documento, garanzie, resi, note, allegati, notifiche, assegnazioni, audit e rilevazione tempi. Una lavorazione può avere più partecipanti contemporanei: `orders.JobParticipation` conserva la sessione di ciascun meccanico, mentre `orders.TimeEvent` registra avvio, pausa, ripresa e chiusura.

Le tabelle dei modelli trasferiti da `fleet` vengono rinominate con migrazioni reversibili; righe, relazioni, permessi e content type esistenti sono conservati. `fleet` mantiene il parco mezzi e le relative fotografie.

Le chiamate accettate compaiono in `/lavori/miei/`. Ogni pausa richiede una causale gestita dall'admin. Il livello profilo `senior`/`manager` o staff può riaprire una lavorazione completata.
