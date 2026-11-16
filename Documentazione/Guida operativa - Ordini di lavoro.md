# Guida operativa — Ordini di lavoro

Procedura per registrare un ordine di lavoro (OdL/RO), affidare le lavorazioni ai meccanici, seguire le attività e chiudere l’ordine in RVKeeper.

## Prima di iniziare

- L’officina deve essere attiva e l’utente deve appartenervi con una membership attiva.
- Il camper deve essere presente nel **Parco mezzi**, appartenere alla stessa officina ed essere collegato a un cliente.
- Per chiamare un meccanico, il suo account deve essere attivo, avere reparto **Technician** ed essere membro attivo della stessa officina. Se non compare nella scelta **Chiama**, controllare tutti e tre i requisiti.
- Un OdL aperto manualmente non crea automaticamente le lavorazioni. Queste vanno aggiunte separatamente in **Lavori e tecnici**, a meno che l’ordine venga generato convertendo un preventivo approvato.

## 1. Aprire l’ordine

1. Nel menu a sinistra aprire **Ordini di lavoro** e scegliere **Nuovo**. In alternativa, dalla scheda del camper usare **Apri ordine di lavoro**: il camper sarà già selezionato.
2. Selezionare il **Camper** corretto. Il cliente viene associato dal proprietario registrato nell’anagrafica; marca, modello, anno e chilometraggio sono riportati dall’anagrafica del camper. Verificare l’anteprima dei dati prima di salvare.
3. Scegliere la classificazione del lavoro e indicare lo stato di garanzia, se pertinente.
4. Compilare **Note di accettazione** con il problema riferito dal cliente e le verifiche concordate. Inserire **Checklist** e **Danni** un elemento per riga: non serve scrivere JSON.
5. Salvare. RVKeeper assegna il numero RO e registra chi ha creato l’ordine. L’ordine appare nella lista con stato **Aperto**.

Se il lavoro parte da un preventivo, registrare e approvare il preventivo, quindi usare **Crea ordine di lavoro**. La conversione crea l’OdL, le lavorazioni dalle righe di manodopera/altro e le richieste ricambi dalle righe ricambio; non creare di nuovo gli stessi elementi.

## 2. Suddividere l’ordine in lavorazioni

1. Aprire **Lavori e tecnici** e selezionare **Nuovo**.
2. Collegare la lavorazione all’OdL e inserire un titolo chiaro (per esempio “Controllo impianto frenante”), descrizione, reparto, specialità, categoria e tempo standard, se noto.
3. Salvare. Creare una lavorazione distinta per ogni attività che deve essere tracciata o affidata separatamente.

Le lavorazioni hanno un proprio stato, indipendente da quello dell’OdL. L’avvio di una lavorazione da parte del meccanico non porta automaticamente l’ordine allo stato **In lavorazione**: l’ufficio aggiorna lo stato dell’ordine nella lista **Ordini di lavoro**.

## 3. Chiamare il meccanico e registrare la presa in carico

1. Nella lista **Lavori e tecnici**, sulla riga della lavorazione, scegliere un nominativo nell’elenco dei meccanici e premere **Chiama**.
2. La chiamata genera una notifica nell’area **Le mie lavorazioni** del meccanico scelto.
3. Il meccanico apre **Le mie lavorazioni** e preme **Accetta e avvia timer**. La lavorazione passa a **In corso** e inizia la registrazione del suo tempo. La presa in carico risulta quindi dall’accettazione della chiamata e dalla sessione attiva.

Un meccanico può anche aprire **Lavori e tecnici** e premere **Avvia / unisciti** per prendere parte autonomamente a una lavorazione aperta. Più meccanici possono partecipare alla stessa lavorazione; ciascuno registra il proprio tempo.

## 4. Gestire avanzamento e imprevisti

- **Pausa:** il meccanico seleziona una causale e preme **Pausa**. Il tempo della sua sessione si ferma.
- **Ripresa:** dalla sessione personale preme **Riprendi timer**; la registrazione riparte.
- **Fine del proprio intervento:** preme **Ferma il mio timer**. Se altri meccanici sono ancora attivi, la lavorazione resta aperta; si completa quando termina anche l’ultima sessione attiva.
- **Ricambi:** creare una richiesta in **Richieste ricambi**, collegandola all’OdL e, quando pertinente, alla lavorazione. Registrare la consegna dalla lista richieste; se la richiesta riguarda un articolo a magazzino, la consegna registra anche lo scarico di giacenza.
- **Garanzia:** aprire una pratica in **Pratiche di garanzia**, collegandola all’ordine e descrivendo componente, difetto e lavoro richiesto. Seguire lì la decisione.
- **Note e documenti:** aggiungere note, assegnazioni o allegati usando le rispettive voci del menu. Collegarli all’OdL o alla lavorazione corretti per mantenerne lo storico.
- **Lavoro aggiuntivo:** aggiornare note e checklist e impostare l’OdL su **Lavori aggiuntivi**. Creare le nuove lavorazioni e, se necessario, richiedere l’approvazione del cliente prima di procedere.

## 5. Verificare e chiudere l’ordine

Prima della chiusura, l’ufficio verifica che le lavorazioni siano completate, che non ci siano sessioni ancora attive, che le richieste ricambi siano state registrate e che note, danni e documenti siano aggiornati. L’app non impedisce di chiudere un ordine con lavorazioni ancora aperte: questa verifica è parte della procedura operativa.

Nella lista **Ordini di lavoro**, usare il selettore di stato sulla riga e premere **Aggiorna**. Il flusso consigliato è:

1. **Aperto** durante l’accettazione e la preparazione.
2. **In lavorazione** quando l’officina avvia le attività.
3. **In attesa di collaudo** al termine delle riparazioni, se serve una verifica finale.
4. **Pronto alla consegna** quando il camper può essere riconsegnato.
5. **Chiuso** dopo il completamento amministrativo e la riconsegna.

Se emergono ulteriori interventi, usare **Lavori aggiuntivi** invece di chiudere. **Annullato** va usato quando l’ordine non deve essere eseguito. La chiusura amministrativa è riservata all’ufficio; l’account meccanico non può impostare **Pronto alla consegna**, **Chiuso** o **Annullato**.

Quando l’OdL è **Chiuso**, l’ufficio può generare **Prospetto PDF** dalla sua riga. Il documento è un riepilogo non fiscale, non sostituisce la fattura. Alla prima generazione si può confermare la marcatura come fatturato; annullando la conferma il PDF si apre senza modificare il flag di fatturazione.

## Stati: ordine e lavorazione

| Oggetto | Stati |
|---|---|
| OdL | Aperto · In lavorazione · In attesa di collaudo · Pronto alla consegna · Lavori aggiuntivi · Chiuso · Annullato |
| Lavorazione | Non iniziato · In corso · In pausa · In attesa ricambi · In attesa garanzia · Completato · Annullato |

Lo stato della lavorazione e quello dell’ordine sono separati: aggiornare l’uno non cambia automaticamente l’altro.
