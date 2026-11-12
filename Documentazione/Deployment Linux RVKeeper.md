---
title: Deployment Linux RVKeeper
aliases:
  - Installazione Linux RVKeeper
  - Provisioning RVKeeper
tags:
  - rvkeeper
  - deployment
  - linux
---

# Deployment Linux RVKeeper

## Ambito

`scripts/provision_server.sh` configura un'installazione nuova su **Debian o Ubuntu** con systemd, PostgreSQL locale, Gunicorn e Nginx. Va eseguito come `root` dalla copia del repository. Non è uno script universale per distribuzioni che usano `dnf`, `pacman` o altri gestori di servizi.

Lo script è idempotente: installa solo i pacchetti mancanti, non riscrive `.env`, applica le migrazioni pendenti compatibili, non elimina database, mantiene inalterati i file systemd/Nginx non gestiti e non riavvia i servizi se la configurazione è già uguale. I file che crea sono marcati `Managed by RVKeeper provision_server.sh`; se trova un file omonimo non marcato, si ferma senza sovrascriverlo.

## Installazione da GitHub

Sostituire l'URL con quello del repository pubblicato. Usare una directory di installazione senza spazi, consigliata `/opt/rvkeeper`.

```bash
sudo apt-get update
sudo apt-get install -y git
sudo git clone https://github.com/OWNER/REPOSITORY.git /opt/rvkeeper
cd /opt/rvkeeper
sudo ./scripts/provision_server.sh
```

Al primo avvio lo script chiede hostname DNS o IPv4. Crea `.venv` e, solo se manca, `.env` con `DJANGO_SECRET_KEY` e password PostgreSQL casuali. I segreti sono esclusi da Git. La configurazione esistente non viene sostituita; deve però indicare PostgreSQL locale (`DB_HOST=127.0.0.1` o `localhost`) e includere l'hostname in `DJANGO_ALLOWED_HOSTS`.

Lo script poi:

1. installa Nginx, PostgreSQL, Python e le dipendenze di compilazione mancanti;
2. crea il ruolo e il database PostgreSQL solo se non esistono;
3. installa `requirements.txt` nella virtualenv e controlla che il database sia vuoto oppure coerente con i modelli;
4. applica le migrazioni e raccoglie i file statici;
5. chiede il superuser se non ne trova già uno attivo;
6. esegue `bootstrap_site`, che crea l'officina demo, il ruolo amministratore, la membership del superuser e i dati dimostrativi;
7. configura il servizio `rvkeeper.service` e il virtual host Nginx, quindi avvia i servizi.

Al termine gli utenti operativi si creano da **Admin → Accounts → Users**, assegnando ciascuno all'officina tramite una membership. Il superuser iniziale viene creato dal provisioning.

## Configurazione e test email

Per abilitare l'invio email dell'applicazione, configurare nel `.env` le variabili `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` e `DEFAULT_FROM_EMAIL`. Il provisioning iniziale lascia il backend email sulla console e i parametri SMTP vuoti: vanno impostati prima di usare l'invio reale. Non inserire password SMTP nella documentazione o in Git; con Gmail usare una password per le app.

Lo script locale `testmail.py` usa invece le variabili `SMTP_USER` e `SMTP_PASSWORD` (facoltativamente `SMTP_HOST` e `SMTP_PORT`, con default `smtp.gmail.com:587`). È escluso da Git e potrebbe non essere presente dopo un clone. Se lo si usa per una prova manuale, definire le variabili nel `.env`, poi caricarle esplicitamente: systemd rende le variabili disponibili al servizio Gunicorn, ma non alla shell interattiva.

```bash
cd /opt/rvkeeper
.venv/bin/python -c 'from dotenv import load_dotenv; load_dotenv(".env"); import runpy; runpy.run_path("testmail.py", run_name="__main__")'
```

Un `KeyError: 'SMTP_USER'` significa che la variabile manca nell'ambiente del processo. Verificare che `SMTP_USER` e `SMTP_PASSWORD` siano valorizzate nel `.env`; non occorre riavviare Gunicorn per eseguire questo test manuale. Perché l'applicazione invii email, impostare anche le variabili `EMAIL_*` usate da Django.

## Dati demo

Il provisioning iniziale crea l'officina configurata da `RVKEEPER_WORKSHOP_NAME` e `RVKEEPER_WORKSHOP_SLUG` nel `.env`. L'attuale `populate_demo_data` richiede un'officina attiva `country=US` e inserisce contatti, ricambi, offerte fornitore e camper fittizi statunitensi. Non crea utenti, ordini di lavoro o preventivi. Il comando è idempotente e può essere rilanciato:

```bash
cd /opt/rvkeeper
./.venv/bin/python manage.py populate_demo_data --workshop rvkeeper-demo
```

Se i dati US non sono adatti alla macchina destinazione, modificare il seed prima della distribuzione o non eseguire il bootstrap demo. I dati `@example`, telefoni `555` e codici `DEMO`/`TEST` sono fittizi e non rappresentano clienti reali.

## HTTPS con Let's Encrypt

Se al primo avvio viene inserito un hostname DNS, lo script chiede se ottenere un certificato Let's Encrypt. Inserendo un'email, richiede il certificato e passa automaticamente Nginx e Django a HTTPS; con invio vuoto lascia il sito in HTTP. Per HTTPS il dominio deve puntare al server e le porte 80 e 443 devono essere aperte sia nel firewall locale sia nel pannello del provider. Gli indirizzi IP non ricevono certificati Let's Encrypt con questo flusso.

Per convertire in seguito un'installazione HTTP, richiedere il certificato con il webroot predisposto dallo script:

Richiedere il certificato con il webroot predisposto dallo script:

```bash
sudo certbot certonly --webroot -w /var/www/rvkeeper-acme -d rvkeeper.example.com
```

Nel `.env` impostare i valori seguenti usando il proprio dominio:

```dotenv
DJANGO_CSRF_TRUSTED_ORIGINS=https://rvkeeper.example.com
DJANGO_SECURE_COOKIES=true
DJANGO_SECURE_SSL_REDIRECT=true
RVKEEPER_TLS_CERTIFICATE=/etc/letsencrypt/live/rvkeeper.example.com/fullchain.pem
RVKEEPER_TLS_KEY=/etc/letsencrypt/live/rvkeeper.example.com/privkey.pem
```

Rieseguire `sudo ./scripts/provision_server.sh`: aggiornerà la configurazione Nginx gestita e passerà a HTTPS. Per ricaricare Nginx dopo il rinnovo del certificato, aggiungere un deploy hook di Certbot che esegua `systemctl reload nginx`.

## Configurazione e dati da proteggere

- `config/settings.py` contiene le impostazioni comuni e i default di sviluppo.
- `config/production_settings.py` aggiunge le impostazioni di produzione; il servizio la seleziona con `DJANGO_SETTINGS_MODULE`.
- `.env.example` documenta le variabili senza contenere credenziali reali.
- `.env`, `.venv/`, `media/`, `staticfiles/`, `*.dump` e `*.backup` non vanno pubblicati.
- Le migrazioni Django **vanno mantenute e versionate**: sono lo schema iniziale che permette a `migrate` di creare un database vergine.
- I dump PostgreSQL non vanno committati. Il provisioning non crea backup automatici e non cancella i dati esistenti.

## Aggiornamento applicativo

Il provisioning serve per l'installazione e la riconciliazione di configurazioni gestite. Per una release successiva, eseguire il deploy del codice con una procedura di backup e applicare le migrazioni dopo aver verificato il target. Non usare questo script come sostituto di un processo di release/rollback.

Comandi operativi:

```bash
sudo systemctl status rvkeeper.service nginx postgresql
sudo journalctl -u rvkeeper.service -f
cd /opt/rvkeeper
./.venv/bin/python manage.py showmigrations
```

Per esportare il database prima di un intervento:

```bash
sudo -u postgres pg_dump -Fc -d rvkeeper > /root/rvkeeper-backup.dump
sudo chmod 600 /root/rvkeeper-backup.dump
```
