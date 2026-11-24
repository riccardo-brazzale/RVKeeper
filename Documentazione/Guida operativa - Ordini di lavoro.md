# Guida operativa — Ordini di lavoro

Procedura per registrare un ordine di lavoro (OdL/RO), affidare le lavorazioni ai meccanici, seguire le attività e chiudere l’ordine in RVKeeper.

## Orientarsi nel menu

- **Dashboard** è il primo collegamento, separato dai gruppi del menu e messo in evidenza in rosso. È disponibile anche agli account meccanico; mostra a ciascuno le informazioni operative del proprio profilo.
- **Anagrafiche** contiene clienti e fornitori, parco mezzi e catalogo ricambi. I listini sono gestiti separatamente.
- **Ordini** contiene la voce **Ordini** (lista degli ordini di lavoro), seguita da **Preventivi**.
- **Ordini di lavorazione** contiene **Le mie lavorazioni**, **Ordini di lavorazione** (elenco e gestione delle singole lavorazioni), **Richieste ricambi**, note, assegnazioni e allegati.
- **Garanzie**, **Report** e **Utility** raccolgono rispettivamente pratiche/resi, report e funzioni di servizio.

I gruppi si aprono e si chiudono cliccando sul titolo. La voce associata alla pagina corrente fa aprire automaticamente il relativo gruppo. Su desktop la barra laterale è allargata per mantenere su una riga i titoli dei gruppi; su smartphone il menu si apre dal pulsante **Menu**.

## Listini

Ogni officina ha i listini **CLIENTE** e **OFFICINE**, mantenuti separatamente. Entrambi possono contenere articoli e tariffe diversi: un articolo presente in un listino non viene copiato né sincronizzato nell'altro. I nuovi codici manodopera si aggiungono dalla pagina del listino **CLIENTE**; non esiste una schermata separata per la loro anagrafica.

Ogni riga di un listino non cliente può avere **Prezzo precedente**, **Prezzo corrente** e **Prezzo futuro**, ciascuno con la propria data di validità iniziale. Le date devono essere in ordine e non possono sovrapporsi: il prezzo applicabile è quello con la data di validità più recente che non supera la data dell'ordine cliente. Il pulsante di rotazione sposta corrente in precedente e futuro in corrente; il precedente viene perso. La rotazione interessa solo le righe con un prezzo futuro valorizzato: le altre righe vengono saltate e i loro prezzi correnti restano invariati.

I clienti usano inizialmente **CLIENTE**. La pagina **Prezzi personalizzati** della scheda cliente apre o crea il listino identificato dal codice cliente, ma quel listino serve esclusivamente a impostare sconti per articolo: non contiene prezzi fissi e non modifica i prezzi dei listini ufficiali. Gli sconti si applicano al prezzo valido del listino scelto; così una variazione del prezzo di listino mantiene lo sconto percentuale del cliente. **OFFICINE** si configura separatamente e non eredita prezzi né sconti automatici.

## Prima di iniziare

- L’officina deve essere attiva e l’utente deve appartenervi con una membership attiva.
- Il camper deve essere presente nel **Parco mezzi**, appartenere alla stessa officina ed essere collegato a un cliente.
- Per chiamare un meccanico, il suo account deve essere attivo, avere reparto **Technician** ed essere membro attivo della stessa officina. Se non compare nella scelta **Chiama**, controllare tutti e tre i requisiti.
- Un OdL aperto manualmente non crea automaticamente le lavorazioni. Un meccanico può aprire una prima attività dalla dashboard quando l'ordine non ne ha ancora; le ulteriori lavorazioni si aggiungono da **Lavori e tecnici**. La conversione di un preventivo approvato crea le attività previste dalle sue righe.

## 1. Aprire l’ordine

1. Nel menu a sinistra aprire il gruppo **Ordini** → la voce **Ordini** e scegliere **Nuovo**. In alternativa, dalla scheda del camper usare **Apri ordine di lavoro**: il camper sarà già selezionato.
2. Selezionare il **Camper** corretto. Il cliente viene associato dal proprietario registrato nell’anagrafica; marca, modello, anno e chilometraggio sono riportati dall’anagrafica del camper. Verificare l’anteprima dei dati prima di salvare.
3. Scegliere la classificazione del lavoro e indicare lo stato di garanzia, se pertinente.
4. Compilare **Note di accettazione** con il problema riferito dal cliente e le verifiche concordate. Inserire **Checklist** e **Danni** un elemento per riga: non serve scrivere JSON.
5. Salvare. RVKeeper assegna il numero RO e registra chi ha creato l’ordine. L’ordine appare nella lista con stato **Aperto**.

Se il lavoro parte da un preventivo, registrare e approvare il preventivo, quindi usare **Crea ordine di lavoro**. La conversione crea l’OdL, le lavorazioni dalle righe di manodopera/altro e le richieste ricambi dalle righe ricambio; non creare di nuovo gli stessi elementi.

## 2. Suddividere l’ordine in lavorazioni

1. Per un ordine senza attività, il meccanico apre l'ordine dalla dashboard e usa **Apri attività**; altrimenti, il personale autorizzato può aprire **Ordini di lavorazione** → **Ordini di lavorazione** e selezionare **Nuovo**.
2. Collegare ogni attività all'OdL e inserire titolo, descrizione, reparto, specialità, categoria e tempo standard, se noto. Il codice mostrato unisce il numero RO e una sottoserie a due cifre (per esempio `RO-2026-0001-01`).
3. Avviare, mettere in pausa, riprendere e chiudere l'attività con i comandi operativi. Gli eventi sono registrati con ora e utente; i report calcolano il tempo escludendo le pause.

Le lavorazioni hanno un proprio stato, indipendente da quello dell'OdL. Il meccanico può portare l'ordine a **In attesa di controllo per fatturazione** solo quando tutte le attività risultano chiuse. L'avvio di un'attività non cambia automaticamente lo stato dell'ordine.

## 3. Chiamare il meccanico e registrare la presa in carico

1. Nella lista **Ordini di lavorazione** → **Ordini di lavorazione**, sulla riga della lavorazione, scegliere un nominativo nell’elenco dei meccanici e premere **Chiama**.
2. La chiamata genera una notifica nell’area **Le mie lavorazioni** del meccanico scelto.
3. Il meccanico apre **Le mie lavorazioni** e preme **Accetta e avvia timer**. La lavorazione passa a **In corso** e inizia la registrazione del suo tempo. La presa in carico risulta quindi dall’accettazione della chiamata e dalla sessione attiva.

Un meccanico può anche aprire **Ordini di lavorazione** → **Ordini di lavorazione** e premere **Avvia / unisciti** per prendere parte autonomamente a una lavorazione aperta. Più meccanici possono partecipare alla stessa lavorazione; ciascuno registra il proprio tempo.

## 4. Gestire avanzamento e imprevisti

- **Pausa:** il menu non preseleziona una causale. Il meccanico deve sceglierne una prima di premere **Pausa**; senza selezione il browser impedisce l'invio e il server non mette in pausa la sessione.
- **Stato e ripresa:** ogni sessione personale mostra in alto lo stato **Attivo** oppure **In pausa**, con la causale della pausa. Per riprendere, premere **Riprendi timer**; la registrazione riparte. Le ultime sessioni terminate restano visibili in **Sessioni recenti** come **Sessione chiusa**.
- **Fine del proprio intervento:** preme **Termina sessione e registra i ricambi usati**, indica i ricambi aggiuntivi prelevati da magazzino e conferma l’elenco, anche se vuoto. Se altri meccanici sono ancora attivi, termina solo la propria sessione; la lavorazione si completa quando termina anche l’ultima sessione attiva.
- **Ricambi richiesti durante la sessione:** in **Le mie lavorazioni**, ogni meccanico con sessione attiva cerca il ricambio per codice o nome, aggiunge una riga per ciascun articolo presente nel catalogo e preme **Invia al magazzino**. Le quantità disponibili vengono impegnate sulla bolla di trasferimento; le quantità mancanti restano in attesa. Il reparto ricambi riceve una notifica.
- **Consegna e indisponibilità:** in **Richieste ricambi**, il magazzino conferma la disponibilità o registra la richiesta come da ordinare. Se il pezzo non è disponibile, può inviare una nota con la data prevista di consegna; il meccanico la vede sull'OdL e la riga resta evidenziata finché non apre l'ordine. La conferma della consegna non scarica subito la giacenza.
- **Ricambi già presenti in officina:** non reinserire la quantità già richiesta e consegnata; indica solo l’eventuale quantità ulteriore prelevata. Se la giacenza non basta, RVKeeper non chiude la sessione e non registra movimenti parziali.
- **Garanzia:** aprire una pratica in **Garanzie** → **Pratiche di garanzia**, collegandola all’ordine e descrivendo componente, difetto e lavoro richiesto. Seguire lì la decisione.
- **Note e documenti:** in **Ordini di lavorazione**, aggiungere note, assegnazioni o allegati usando le rispettive voci. Collegarli all’OdL o alla lavorazione corretti per mantenerne lo storico.
- **Lavoro aggiuntivo:** aggiornare note e checklist e impostare l’OdL su **Lavori aggiuntivi**. Creare le nuove lavorazioni e, se necessario, richiedere l’approvazione del cliente prima di procedere.

## 5. Verificare e chiudere l’ordine

Prima del controllo per la fatturazione, verificare che tutte le attività siano chiuse, che non ci siano sessioni attive e che richieste ricambi, note e documenti siano aggiornati. Quando il magazzino riceve i ricambi ordinati, le quantità vengono caricate a stock e assegnate alle richieste in attesa. Alla chiusura dell'OdL il sistema scarica in modo atomico i ricambi impegnati; se l'ordine viene annullato, gli impegni vengono rilasciati senza movimenti di scarico.

Nel gruppo **Ordini**, aprire la voce **Ordini**, usare il selettore di stato sulla riga e premere **Aggiorna**. Il flusso consigliato è:

1. **Aperto** durante l'accettazione e la preparazione.
2. **In lavorazione** durante le attività.
3. **In attesa di controllo per fatturazione** dopo la chiusura di tutte le attività.
4. **Pronto alla consegna** quando il camper può essere riconsegnato.
5. **Chiuso** dopo il completamento amministrativo; in questa transizione avviene lo scarico definitivo delle quantità impegnate.

Se emergono ulteriori interventi, usare **Lavori aggiuntivi** invece di chiudere. **Annullato** va usato quando l’ordine non deve essere eseguito. La chiusura amministrativa è riservata all’ufficio; l’account meccanico non può impostare **Pronto alla consegna**, **Chiuso** o **Annullato**.

Quando l'OdL è **Chiuso**, nel gruppo **Ordini** → voce **Ordini**, l'ufficio può aprire **Prezzi fatturazione** dalla riga o dalla scheda dell'ordine. La pagina propone i prezzi validi alla data di apertura dell'OdL, già scontati per il cliente; l'ufficio può modificare separatamente il prezzo unitario di ogni ricambio scaricato, consumo di magazzino e tariffa oraria di ogni lavorazione fatturabile. Salvando, i prezzi personalizzati restano memorizzati sulle righe dell'OdL.

Da **Prezzi fatturazione** si può poi aprire **Prospetto PDF**. Il documento usa i prezzi salvati per riga e, dove non è stato impostato un prezzo personalizzato, ricalcola il prezzo valido alla data dell'ordine. Riepiloga ricambi, consumi, tempi e manodopera; è un documento non fiscale e non sostituisce la fattura. Alla generazione si può confermare la marcatura come fatturato; annullando la conferma il PDF si apre senza modificare il flag di fatturazione.

## Ordini fornitori e listini

Solo magazziniere e amministratori possono gestire gli acquisti. Le richieste non coperte dallo stock possono essere aggiunte a un ordine fornitore aperto; per più offerte, viene usato il fornitore preferito o, se non impostato, quello con il prezzo netto più basso. Il prezzo e lo sconto di un listino fornitore valido alla data dell'ordine sono salvati come valori iniziali e possono essere modificati dal magazziniere. Il minimo d'ordine e il multiplo confezione arrotondano sempre la quantità per eccesso.

Alla ricezione, inserire il numero della bolla e le quantità arrivate per ciascuna riga. Sono ammesse ricezioni parziali e più bolle per ordine; ogni bolla può essere stampata in PDF per la contabilità. L'ordine si può saldare anche se restano quantità non ricevute. I listini fornitori si importano da **Listini fornitori** in formato CSV o XLSX; la schermata mostra gli errori di validazione e le righe valide importate.

### Report di ordini e tempi per tecnico

Nel gruppo **Reports** è disponibile il consuntivo delle sessioni, filtrabile per tecnico e intervallo di date (all’apertura mostra il mese corrente). Il dettaglio riporta per ogni sessione l’ordine, la lavorazione, il tecnico, l’inizio, la fine e la durata; gli intervalli che attraversano i confini del periodo vengono conteggiati solo per la parte inclusa. La pagina mostra inoltre i totali per ordine e per tecnico. **Esporta PDF** e **Esporta Excel** scaricano lo stesso dettaglio e gli stessi totali; il file Excel contiene fogli separati per dettaglio, totali per ordine e totali per tecnico. È un consuntivo dei tempi registrati, non una fattura.

## Stati: ordine e lavorazione

| Oggetto | Stati |
|---|---|
| OdL | Aperto · In lavorazione · In attesa di collaudo · Pronto alla consegna · Lavori aggiuntivi · Chiuso · Annullato |
| Lavorazione | Da iniziare · In corso · In pausa · In attesa dei ricambi · In attesa della garanzia · Chiusa · Annullata |

Lo stato della lavorazione e quello dell’ordine sono separati: aggiornare l’uno non cambia automaticamente l’altro.
