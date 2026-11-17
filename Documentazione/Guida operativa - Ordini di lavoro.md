# Guida operativa — Ordini di lavoro

Procedura per registrare un ordine di lavoro (OdL/RO), affidare le lavorazioni ai meccanici, seguire le attività e chiudere l’ordine in RVKeeper.

## Orientarsi nel menu

- **Dashboard** è il primo collegamento, separato dai gruppi del menu e messo in evidenza in rosso. È disponibile anche agli account meccanico; mostra a ciascuno le informazioni operative del proprio profilo.
- **Anagrafiche** contiene clienti e fornitori, parco mezzi, articoli di manodopera e catalogo ricambi.
- **Ordini** contiene la voce **Ordini** (lista degli ordini di lavoro), seguita da **Preventivi**.
- **Ordini di lavorazione** contiene **Le mie lavorazioni**, **Ordini di lavorazione** (elenco e gestione delle singole lavorazioni), **Richieste ricambi**, note, assegnazioni e allegati.
- **Garanzie**, **Report** e **Utility** raccolgono rispettivamente pratiche/resi, report e funzioni di servizio.

I gruppi si aprono e si chiudono cliccando sul titolo. La voce associata alla pagina corrente fa aprire automaticamente il relativo gruppo. Su desktop la barra laterale è allargata per mantenere su una riga i titoli dei gruppi; su smartphone il menu si apre dal pulsante **Menu**.

## Prima di iniziare

- L’officina deve essere attiva e l’utente deve appartenervi con una membership attiva.
- Il camper deve essere presente nel **Parco mezzi**, appartenere alla stessa officina ed essere collegato a un cliente.
- Per chiamare un meccanico, il suo account deve essere attivo, avere reparto **Technician** ed essere membro attivo della stessa officina. Se non compare nella scelta **Chiama**, controllare tutti e tre i requisiti.
- Un OdL aperto manualmente non crea automaticamente le lavorazioni. Queste vanno aggiunte separatamente in **Lavori e tecnici**, a meno che l’ordine venga generato convertendo un preventivo approvato.

## 1. Aprire l’ordine

1. Nel menu a sinistra aprire il gruppo **Ordini** → la voce **Ordini** e scegliere **Nuovo**. In alternativa, dalla scheda del camper usare **Apri ordine di lavoro**: il camper sarà già selezionato.
2. Selezionare il **Camper** corretto. Il cliente viene associato dal proprietario registrato nell’anagrafica; marca, modello, anno e chilometraggio sono riportati dall’anagrafica del camper. Verificare l’anteprima dei dati prima di salvare.
3. Scegliere la classificazione del lavoro e indicare lo stato di garanzia, se pertinente.
4. Compilare **Note di accettazione** con il problema riferito dal cliente e le verifiche concordate. Inserire **Checklist** e **Danni** un elemento per riga: non serve scrivere JSON.
5. Salvare. RVKeeper assegna il numero RO e registra chi ha creato l’ordine. L’ordine appare nella lista con stato **Aperto**.

Se il lavoro parte da un preventivo, registrare e approvare il preventivo, quindi usare **Crea ordine di lavoro**. La conversione crea l’OdL, le lavorazioni dalle righe di manodopera/altro e le richieste ricambi dalle righe ricambio; non creare di nuovo gli stessi elementi.

## 2. Suddividere l’ordine in lavorazioni

1. Aprire **Ordini di lavorazione** → **Ordini di lavorazione** e selezionare **Nuovo**.
2. Collegare la lavorazione all’OdL e inserire un titolo chiaro (per esempio “Controllo impianto frenante”), descrizione, reparto, specialità, categoria e tempo standard, se noto.
3. Salvare. Creare una lavorazione distinta per ogni attività che deve essere tracciata o affidata separatamente.

Le lavorazioni hanno un proprio stato, indipendente da quello dell’OdL. L’avvio di una lavorazione da parte del meccanico non porta automaticamente l’ordine allo stato **In lavorazione**: l’ufficio aggiorna lo stato dell’ordine nella lista **Ordini di lavoro**.

## 3. Chiamare il meccanico e registrare la presa in carico

1. Nella lista **Ordini di lavorazione** → **Ordini di lavorazione**, sulla riga della lavorazione, scegliere un nominativo nell’elenco dei meccanici e premere **Chiama**.
2. La chiamata genera una notifica nell’area **Le mie lavorazioni** del meccanico scelto.
3. Il meccanico apre **Le mie lavorazioni** e preme **Accetta e avvia timer**. La lavorazione passa a **In corso** e inizia la registrazione del suo tempo. La presa in carico risulta quindi dall’accettazione della chiamata e dalla sessione attiva.

Un meccanico può anche aprire **Ordini di lavorazione** → **Ordini di lavorazione** e premere **Avvia / unisciti** per prendere parte autonomamente a una lavorazione aperta. Più meccanici possono partecipare alla stessa lavorazione; ciascuno registra il proprio tempo.

## 4. Gestire avanzamento e imprevisti

- **Pausa:** il menu non preseleziona una causale. Il meccanico deve sceglierne una prima di premere **Pausa**; senza selezione il browser impedisce l'invio e il server non mette in pausa la sessione.
- **Stato e ripresa:** ogni sessione personale mostra in alto lo stato **Attivo** oppure **In pausa**, con la causale della pausa. Per riprendere, premere **Riprendi timer**; la registrazione riparte. Le ultime sessioni terminate restano visibili in **Sessioni recenti** come **Sessione chiusa**.
- **Fine del proprio intervento:** preme **Termina sessione e registra i ricambi usati**, indica i ricambi aggiuntivi prelevati da magazzino e conferma l’elenco, anche se vuoto. Se altri meccanici sono ancora attivi, termina solo la propria sessione; la lavorazione si completa quando termina anche l’ultima sessione attiva.
- **Ricambi richiesti durante la sessione:** in **Le mie lavorazioni**, ogni meccanico con sessione attiva cerca il ricambio per codice o nome, aggiunge una riga per ciascun articolo presente nel catalogo e preme **Invia al magazzino**. L'unità viene mostrata automaticamente in base all'articolo selezionato. Prima dell'invio compare una conferma; confermandola, ogni riga resta collegata alla lavorazione e all’OdL e il reparto ricambi riceve una notifica (se non ci sono utenti attivi nel reparto, la notifica è visibile all’officina). Se il ricambio non è nel catalogo, aggiungerlo prima al catalogo dell'officina. **Aggiungi ricambio** e **Invia al magazzino** sono affiancati e hanno colori distinti; ogni riga si può rimuovere con il pulsante rosso **Rimuovi riga**.
- **Consegna del magazzino:** in **Richieste ricambi**, il magazzino usa **Conferma consegna** sulla singola riga quando consegna il ricambio. La riga mostra quindi la spunta **Ricevuto**; per gli articoli a catalogo, la conferma registra anche il movimento di scarico dalla giacenza.
- **Ricambi già presenti in officina:** non reinserire la quantità già richiesta e consegnata; indica solo l’eventuale quantità ulteriore prelevata. Se la giacenza non basta, RVKeeper non chiude la sessione e non registra movimenti parziali.
- **Garanzia:** aprire una pratica in **Garanzie** → **Pratiche di garanzia**, collegandola all’ordine e descrivendo componente, difetto e lavoro richiesto. Seguire lì la decisione.
- **Note e documenti:** in **Ordini di lavorazione**, aggiungere note, assegnazioni o allegati usando le rispettive voci. Collegarli all’OdL o alla lavorazione corretti per mantenerne lo storico.
- **Lavoro aggiuntivo:** aggiornare note e checklist e impostare l’OdL su **Lavori aggiuntivi**. Creare le nuove lavorazioni e, se necessario, richiedere l’approvazione del cliente prima di procedere.

## 5. Verificare e chiudere l’ordine

Prima della chiusura, l’ufficio verifica che le lavorazioni siano completate, che non ci siano sessioni ancora attive, che le richieste ricambi siano state registrate e che note, danni e documenti siano aggiornati. Quando un meccanico termina la propria sessione, registra i ricambi di magazzino utilizzati nel modulo di conferma; se collaborano più meccanici, ogni sessione si chiude separatamente e la lavorazione si completa solo alla fine dell’ultima sessione. L’app non impedisce di chiudere un ordine con lavorazioni ancora aperte: questa verifica è parte della procedura operativa.

Nel gruppo **Ordini**, aprire la voce **Ordini**, usare il selettore di stato sulla riga e premere **Aggiorna**. Il flusso consigliato è:

1. **Aperto** durante l’accettazione e la preparazione.
2. **In lavorazione** quando l’officina avvia le attività.
3. **In attesa di collaudo** al termine delle riparazioni, se serve una verifica finale.
4. **Pronto alla consegna** quando il camper può essere riconsegnato.
5. **Chiuso** dopo il completamento amministrativo e la riconsegna.

Se emergono ulteriori interventi, usare **Lavori aggiuntivi** invece di chiudere. **Annullato** va usato quando l’ordine non deve essere eseguito. La chiusura amministrativa è riservata all’ufficio; l’account meccanico non può impostare **Pronto alla consegna**, **Chiuso** o **Annullato**.

Quando l’OdL è **Chiuso**, nel gruppo **Ordini** → voce **Ordini**, l’ufficio può generare **Prospetto PDF** dalla sua riga. Il documento riepiloga i ricambi consegnati e quelli aggiuntivi consumati da giacenza, oltre a tempi e manodopera; è un riepilogo non fiscale e non sostituisce la fattura. Alla prima generazione si può confermare la marcatura come fatturato; annullando la conferma il PDF si apre senza modificare il flag di fatturazione.

### Report di ordini e tempi per tecnico

Nel gruppo **Reports** è disponibile il consuntivo delle sessioni, filtrabile per tecnico e intervallo di date (all’apertura mostra il mese corrente). Il dettaglio riporta per ogni sessione l’ordine, la lavorazione, il tecnico, l’inizio, la fine e la durata; gli intervalli che attraversano i confini del periodo vengono conteggiati solo per la parte inclusa. La pagina mostra inoltre i totali per ordine e per tecnico. **Esporta PDF** e **Esporta Excel** scaricano lo stesso dettaglio e gli stessi totali; il file Excel contiene fogli separati per dettaglio, totali per ordine e totali per tecnico. È un consuntivo dei tempi registrati, non una fattura.

## Stati: ordine e lavorazione

| Oggetto | Stati |
|---|---|
| OdL | Aperto · In lavorazione · In attesa di collaudo · Pronto alla consegna · Lavori aggiuntivi · Chiuso · Annullato |
| Lavorazione | Non iniziato · In corso · In pausa · In attesa ricambi · In attesa garanzia · Completato · Annullato |

Lo stato della lavorazione e quello dell’ordine sono separati: aggiornare l’uno non cambia automaticamente l’altro.
