# Ordini e lavorazioni

Questa app possiede le tabelle `orders_*` per ordini di lavoro, lavorazioni, chiamate ai meccanici e causali pausa. Una lavorazione può avere N partecipanti contemporanei: `fleet.JobParticipation` tiene la sessione di ciascun meccanico, mentre `fleet.TimeEvent` registra avvio, pausa, ripresa e chiusura.

Le chiamate accettate compaiono in `/lavori/miei/`. Ogni pausa richiede una causale gestita dall'admin. Il livello profilo `senior`/`manager` o staff può riaprire una lavorazione completata.
