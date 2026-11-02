# Contesto corrente — 26 ottobre 2026

Leggere questo documento per riprendere il progetto esistente.
**Stato corrente:** [21_CORREZIONE_COMPLETEZZA.md](21_CORREZIONE_COMPLETEZZA.md).
Corrette tutte le omissioni accertate nel registro 20: 147 riferimenti del browser
ora presenti, 76 file prima mancanti scaricati e archiviati; due pagine aggiornate.
Nuovo catalogo: 642 risorse / 516 file. GUI aggiornata aperta e due casi verificati
visivamente. Linux 3.10/3.12/3.14: 140 passati ciascuno; Windows: 136 + 4 skip.
Restano i 37 avvisi precedenti e il relativo gate di completezza, distinti dai casi
del registro 20 appena risolti. I paragrafi seguenti conservano lo storico.
**Aggiornamento più recente:** [20_CONFRONTO_SITO_GUI.md](20_CONFRONTO_SITO_GUI.md).
Browser autenticato: aperte 279 sezioni dei 32 corsi. Trovati 33 riferimenti a materiali
didattici assenti dal catalogo corrente della GUI: 23 link con time e 10 allegati dei
compiti Python. Assenti anche 40 file consegnati e 3 feedback. Nessuna correzione
runtime ancora applicata; il precedente confronto hash non certificava completezza.
Evidenze finali e gate: [18_COLLAUDO_PRODUZIONE.md](18_COLLAUDO_PRODUZIONE.md).
Ultima verifica: [19_INTEGRITA_FAD.md](19_INTEGRITA_FAD.md): 438 file identici alla FAD
con nuovi GET e SHA256, 23 quiz identici; una pagina locale da aggiornare (100 caratteri
aggiunti nella versione remota). Tutti i 458 BLOB riletti senza errori.
I documenti 12–17 conservano lo storico; i loro problemi superati non sono lo stato corrente.

## Stato e decisioni dell'utente

- Lavorare esclusivamente in 10_Programmazione_Python/Final exams project/, codice in app/.
- Continuare FAD Downloader 0.2.0; non ricominciare da zero.
- Destinazione produzione: Linux. **Gate NO-GO:** restano 16 materiali non riconosciuti.
- Upload compiti rimandato. Nessun admin fra gli utenti DB.
- L'utente ha autorizzato il collaudo in sola lettura di tutti i corsi FAD accessibili.
  Scansione, download e seconda passata sono stati eseguiti; non ripeterli senza un motivo nuovo.
- Nessun upload, consegna, nuovo tentativo quiz, push o pubblicazione eseguito.
- Le credenziali FAD sono lette internamente dal .env: non stamparle o leggerne i valori nei prompt.
  Non riportare HTML privato, nomi dei corsi, materiali, voti o risposte.
- R03 e le regole comuni sono riallineati alla scelta .env già registrata nel documento 13:
  niente keyring nel login corrente, salvataggio dopo successo, GUI mascherata e cancellazione esplicita.
  Il file non è cifrato; i riferimenti keyring nel piano iniziale sono storici.

## Verifiche concluse

- Linux con Xvfb e filesystem POSIX: 129 test passati su ciascuna versione
  Python 3.10.22, 3.12.15 e 3.14.4, nessuno saltato.
- Wheel installata in virtualenv Linux pulito e offline: suite completa superata.
- Windows Python 3.14.7: 125 passati, 4 saltati (Tk assente e test POSIX).
- Ruff, Bandit, pip check e audit online del runtime Linux senza segnalazioni.
- Build wheel/sdist e lock SHA256 di 22 dipendenze runtime Linux verificati.
  Wheelhouse offline specifico per Linux x86_64 / CPython 3.14.
- Benchmark sintetico: 1.000 risorse GUI, 10.000 record nel manifest;
  i comandi UI misurati rientrano nei 200 ms. Misure e limiti nel registro 18.
- Il precedente fallimento permessi 0600 sul mount Windows è superato nella prova POSIX.
  Non significa che il mount Windows offra gli stessi permessi.
- La GUI Windows non trova init.tcl nell'installazione Python globale; GUI Linux verificata con Xvfb.

## Collaudo FAD reale

32 corsi, 279 sezioni, 564 risorse rilevate.
438 file, 23 review quiz completati e 2 pagine sono stati verificati attraverso
la prima prova e il ritest della correzione. Le 101 altre attività sono link, googlemeet e consegne.

Prima passata: 462 scaricate, 1 pagina non supportata.
Seconda: 438 invariate, 24 export aggiornati, stessa pagina esclusa.
Verifica del primo workspace: 463 file, 0 problemi. SQLite integro.
926 operazioni nello storico; PDF di 50 pagine aperto; hash di un BLOB campione verificato.

La pagina aveva una generalbox senza no-overflow: corretto exporter.py con fallback
limitato alla pagina Moodle, più due test per contenuto, sanitizzazione ed esclusione navigazione.
Ritest reale di entrambe le pagine: 2 scaricate, 0 problemi, testo visibile preservato.
Il ritest usa un workspace/DB separato: il vecchio report non è stato riscritto come successo.

## Problemi ancora aperti

- 16 avvisi materiali: 15 risposte HTML del modulo resource con notifica e senza file
  riconosciuto; 1 file HTML diretto da pluginfile. Non dichiararli vuoti, inesistenti o risolti.
- 1 collegamento verso un host diverso rifiutato dalla policy: non allargare il confine
  di fiducia per far sparire l'avviso. Nessuna credenziale inviata all'host esterno.
- 20 quiz senza tentativi completati/revisionabili riconosciuti: non crearne o inviarne di nuovi.
- DNS bloccante, crash e carico non sono coperti in modo esaustivo; nessun desktop
  Linux autonomo provato. Nessun libro disponibile nel catalogo reale di questa prova.
- Non dichiarare tutti i criteri di accettazione chiusi solo perché la suite è verde.

## Mappa e strumenti

- app/README.md: avvio, credenziali, utenti, GUI/CLI e installazione candidata.
- app/src/fad_downloader/: gui/cli; domain/services; moodle/network/exporter;
  storage/state; database/pdf_reports; env_config/credentials/observability.
- app/tests/: test sintetici; conftest isola configurazione e blocca rete esterna.
- app/check_windows.ps1: pipeline Windows che si ferma agli errori.
- app/check_production_linux.sh: mount POSIX temporaneo sotto il progetto, test come
  utente ordinario, installazione pulita e opzionalmente matrice --compat.
  In questo workspace usa in lettura l'interprete preesistente ~/fad-v001-venv.
- app/prepare_linux_lock.py: wheelhouse, lock con hash e manifest di integrità.
- app/smoke_release.py, stress_acceptance.py: prove offline sintetiche.
- app/live_acceptance.py e live_scan_diagnostics.py: comandi reali espliciti;
  non includerli nella suite automatica.
- app/.verification-artifacts/: log, pacchetti, freeze, audit, hash e misure; ignorati da Git.
- app/.verification-live/: dati FAD privati e DB di collaudo; ignorati da Git.
  Gli utenti di questi DB hanno password casuali non conservate: non sono account di produzione.
- Non eseguire i vecchi check_linux.sh/check_release.sh senza leggerli: scrivono sotto HOME.
- Nessuna modifica agli esercizi. La cartella non tracciata degli esercizi sul modulo OS
  è esterna al progetto finale e va lasciata intatta.

## Ripresa operativa

Controllare Git status e preservare il diff. Leggere il registro 18 e i contratti pertinenti.
Prossimo lavoro: chiarire i 16 materiali con evidenza strutturale o confronto browser,
definire la gestione sicura del file HTML come materiale e aggiungere regressioni.
Non cambiare requisiti o segnare avvisi come successi per rendere verde il rilascio.
Dopo nuove modifiche eseguire i controlli pertinenti e aggiornare il gate.
