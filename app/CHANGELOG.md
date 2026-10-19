# Changelog

## 0.2.0 — 15 ottobre 2026

- Archivio SQLite con utenti applicativi ordinari, senza amministratore, separati dagli account FAD.
- Password DB con scrypt, sessioni a scadenza, storico e BLOB filtrati per proprietario.
- Archiviazione automatica dei file principali e degli allegati in blocchi BLOB da 1 MiB.
- Archivio grafico, ripristino dei BLOB e importazione dei workspace delle versioni precedenti.
- Report personale PDF con ReportLab, conteggi, tabelle multipagina e intestazioni ripetute.
- Due utenti demo in database separato, nuovi comandi CLI e test di separazione dei dati.

### Credenziali persistenti nel `.env` — 14 ottobre 2026

GUI precompilata con username e password mascherata dal file; salvataggio automatico
dopo login riuscito; ricaricamento esplicito e cancellazione dal file. Variabili d'ambiente
e portachiavi esclusi dal login. Scrittura atomica, conservazione di altre chiavi/commenti,
caratteri speciali preservati, credenziali precedenti conservate dopo login fallito.

### Sezioni del tema Snap — 14 ottobre 2026

Caricamento delle sezioni renderizzate su richiesta dal tema Snap, tramite
`core_get_fragment` limitato a `theme_snap/section` e parametri numerici di lettura.
Le sezioni sono entità persistenti distinte dalle risorse: la GUI conserva sezioni vuote,
corsi senza download e sezioni omonime con ID distinti. Risorse associate all'indice reale
della sezione. Nessuna esecuzione dei JavaScript restituiti dai frammenti.

### Correzione salvataggio catalogo — 14 ottobre 2026

Le attività non supportate (`assign`, `url` e altri riferimenti locali `mod/*/view.php`)
possono essere registrate come metadati del catalogo. La policy HTTP rimane invariata:
non vengono visitate o eseguite dal downloader. ID e parametro redirect dei link validati;
catalogo prevalidato prima di modificare il manifest. Test per conservazione dello stato,
rifiuto di origini/azioni estranee e mancata esecuzione delle attività non supportate.

### Monitoraggio — 14 ottobre 2026

Log strutturati JSONL a rotazione, livelli configurabili e pulsante GUI «Apri log».
Tracciamento di operazioni e worker, auth, rete, scansione, download, filesystem,
configurazione, backup e integrità. Esclusione di segreti, contenuti privati e messaggi
grezzi delle eccezioni; test per riservatezza, rotazione, correlazione e CLI.

### Correzione login — 14 ottobre 2026

Consentito il redirect Moodle `login/index.php?testsession=ID` per GET con ID numerico
positivo, oltre a `my/index.php` e `index.php`. Il POST delle credenziali non viene
ripetuto durante i redirect. Test reale riuscito: login, elenco di 31 corsi, logout.
Test di regressione per il redirect valido e per parametri non consentiti.

## 0.1.0 — 14 ottobre 2026

- Scansione automatica dopo il login, catalogo persistente e apertura offline.
- Nuove risorse e titoli aggiornati evidenziati; contenuti non più rilevati conservati.
- Sottocartelle degli allegati Moodle e modello del nome delle attività.
- Configurazione globale XDG, impostazioni workspace e limiti validati.
- Piano persistente, una riautenticazione automatica per download, account verificato.
- Copie alternative per i conflitti, backup e ripristino dello stato, inventario temporanei.
- Report con unità separate e scansione parziale; indice raggruppato per corso.
- Logout remoto esplicito, identità quiz indipendente dalla pagina, fallback dei libri.
- Comandi CLI aggiuntivi: catalog, backup, restore, recovery, download --resume/--copy-conflicts.

Accesso alla FAD reale tentato: il server ha rifiutato le credenziali locali.
La compatibilità Moodle autenticata non è ancora attestata.

## 0.0.1 — 14 ottobre 2026

Prima implementazione autonoma con GUI Tkinter, CLI, demo offline, adattatore Moodle,
download, export HTML dei tentativi completati, impostazioni di nomenclatura,
manifest, verifica SHA-256 e test automatici.

Versione sperimentale: il collaudo sulla FAD reale è ancora da eseguire.
Questa versione non certifica il completamento di tutti i requisiti del piano finale.

Aggiornamento: lettura delle credenziali da `.env` richiesta dall'utente, con variabili
`FAD_USERNAME` e `FAD_PASSWORD`, scelta `--env-file`, esclusione Git e test dedicati.
