# Versione 0.1.0 — 14 ottobre 2026

Prima versione con il flusso applicativo completo, sviluppata in `app/`.
I controlli automatici usano dati sintetici; il completamento del codice non equivale
alla validazione della FAD reale o al superamento di tutti i gate del piano.

## Nuove funzioni

Scansione automatica dopo il login; catalogo persistente; consultazione offline;
nuove risorse e metadati aggiornati evidenziati; conservazione dei contenuti non più rilevati;
sottocartelle Moodle; template delle attività; configurazione XDG e limiti validati;
piano recuperabile; riautenticazione controllata; copie alternative dei conflitti;
backup e ripristino dello stato; inventario dei temporanei; indice per corso;
logout remoto esplicito; conteggi distinti di risorse e file.

## Verifiche effettuate

| Prova | Esito |
|---|---|
| Test Windows, Python 3.14 | 70 passati, 1 saltato perché specifico POSIX |
| Test Ubuntu 26.04 in WSL, Python 3.14.4, Xvfb | 71 passati, nessuno saltato |
| Ruff | Nessuna segnalazione |
| Bandit | Nessuna segnalazione; non equivale a certificazione di sicurezza |
| GUI | Cattura osservata, nuovo percorso demo/offline/backup provato automaticamente |
| Build e installazione isolata Ubuntu | Wheel 0.1.0 installato, demo scaricata e catalogo letto |
| Verifica del wheel installato | 3 file verificati, 0 problemi |
| Audit delle dipendenze runtime | Nessuna vulnerabilità nota rilevata alla data della prova |
| Login reale dalla configurazione locale | Server raggiunto; login rifiutato; nessuna scansione autenticata eseguita |

Il test reale ha usato soltanto login e lettura delle pagine necessarie; nessuna password,
cookie, sesskey, pagina privata o credenziale è inclusa in questa evidenza.
L'integrazione reale non è dichiarata riuscita.

## Copertura dei requisiti

| Requisiti | Implementazione e prova | Verifica residua |
|---|---|---|
| R01, R22 | GUI e CLI su Ubuntu WSL; wheel isolato; XDG | Desktop Linux autonomo e Python 3.10/3.12 |
| R02, R03 | Login, logout, `.env`, portachiavi, separazione account | Login valido e portachiavi Linux desktop |
| R04, R05 | Scan, persistenza, confronto cataloghi, marker e mapping | Completezza sul Moodle reale |
| R06, R07, R08 | Ricerca, filtri, selezione, anteprima e template | Usabilità su grandi cataloghi reali |
| R09 | Percorsi API/mod_folder, collisioni e scrittura sicura | Cartelle reali con tema/plugin diversi |
| R10, R11 | Export passivo, libri e quiz completati, paginazione | Fedeltà delle review e dei libri reali |
| R12, R19, R20 | Hash, 304, conflitti, copia alternativa, generazioni | Rete e crash controllati più estesi |
| R13, R14, R15 | Piano persistente, una riautenticazione, annullamento, retry | Tempi di annullamento e GUI sotto carico |
| R16, R18 | Indice raggruppato, catalogo e report offline | Accessibilità e navigazione manuale Linux |
| R17, R24 | Servizi comuni, CLI, esiti e unità separate | Ulteriore parità sui casi reali |
| R21, R23 | Limiti validati, policy rete e sanitizzazione | Misure DNS, TLS e connessioni lente controllate |
| R25 | Schema 1 compatibile; futuro rifiutato; backup, recupero JSON corrotto e temporanei | Prove di crash durante ripristino composto |

## Limiti dichiarati

Aggiornamento richiesto dall'utente: credenziali caricate e salvate soltanto nel `.env`.
GUI precompilata con password mascherata; scrittura automatica dopo login riuscito,
conservazione dei valori precedenti se il login fallisce, ricaricamento e cancellazione espliciti.
Le variabili d'ambiente e il portachiavi non prevalgono più sul file. I test usano file temporanei
e verificano caratteri speciali, conservazione delle altre impostazioni e flusso GUI.
Regressione: Windows 104 passati/1 saltato; Ubuntu WSL 105 passati/0 saltati.

Correzione sezioni Snap: l'HTML iniziale conteneva solo la sezione 0; le altre venivano
caricate tramite il frammento `theme_snap/section`. Adattatore e policy aggiornati per
questa sola chiamata di lettura, con parametri controllati e nessuna esecuzione JavaScript.
Riferimenti tecnici: [caricamento sezioni Snap](https://github.com/open-lms-open-source/moodle-theme_snap/blob/MOODLE_311_STABLE/amd/src/section_asset_management.js)
e [API frammenti Moodle](https://github.com/moodle/moodle/blob/MOODLE_311_STABLE/lib/amd/src/fragment.js).
Prova reale su catalogo temporaneo: 31 corsi, 272 sezioni, 527 risorse; tutte le sezioni
presenti nei menu Snap caricate, nessuna marcata non disponibile. Salvataggio e riapertura
riusciti. Rimangono 56 avvisi di scansione; non si attesta ancora completezza di ogni risorsa.
Regressione: Windows 96 passati/1 saltato; Ubuntu WSL 97 passati/0 saltati.
Le sezioni sono persistite anche quando vuote o omonime; vecchi cataloghi senza il campo
`sections` restano leggibili e possono essere aggiornati con una nuova scansione.

Correzione catalogo: riprodotto il blocco su 6 attività `url` e 2 `assign`.
I riferimenti vengono ora conservati come metadati senza autorizzarne le richieste HTTP.
Prova reale su workspace temporaneo: scansione, salvataggio e riapertura riusciti,
31 corsi e 57 risorse; sessione autenticata verificata dopo il salvataggio; logout riuscito.
La scansione rimane parziale con 33 avvisi: non attesta completezza di tutte le attività.
Regressione Windows: 89 passati, 1 saltato perché specifico POSIX.

Aggiornamento monitoraggio: log JSONL a rotazione con livelli CLI e accesso dalla GUI.
Copertura di auth, rete, worker, scansione, pianificazione, download, export, configurazione,
scritture atomiche, lock, recupero e verifica. Nessun valore di credenziale o contenuto remoto
nei log; nomi route e codici controllati. Test aggiuntivi per esclusione dei segreti,
permessi POSIX, rotazione, correlazione, filtri di livello e copertura CLI.
Esito aggiornato: Windows 82 passati/1 saltato; Ubuntu WSL 83 passati/0 saltati.

Il backup riguarda lo stato, non gli allegati. Le vecchie generazioni restano sul disco.
La scansione può essere parziale e lo dichiara. Tipi quiz sconosciuti vengono rifiutati.
SSO/MFA, video esterni, SCORM, forum, PDF dei test e HTTP Range restano fuori ambito.
Un DNS bloccato può ritardare l'annullamento; il ripristino di più JSON non è una singola transazione.
Le dipendenze provate sono registrate, ma il lock universale con hash resta da completare.

## Prossima verifica necessaria

Aggiornamento login: con il `.env` corretto è stato riprodotto un blocco della policy
sul redirect `login/index.php?testsession=ID`. La policy è stata corretta e limita
il parametro a un singolo ID numerico positivo su GET. Verifica reale successiva:
login riuscito, 31 corsi accessibili, logout riuscito. Nessuna credenziale registrata.
Regressione Windows: 76 test passati, 1 saltato perché specifico POSIX.
Regressione Ubuntu WSL con Xvfb: 77 test passati, nessuno saltato.
Le prove di scansione delle attività ed esportazione reale restano aperte.

Proseguire F0A: confronto dei corsi, delle cartelle,
di una pagina/libro e di un tentativo quiz completato con quanto visibile nel browser.
I gate finali restano aperti fino a questa prova e alle misure di robustezza previste.
