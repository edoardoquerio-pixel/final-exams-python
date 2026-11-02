# 21 - Correzione delle omissioni accertate nel confronto sito → app

26 ottobre 2026. Corrette le omissioni documentate nel registro 20:
**tutti i 147 riferimenti osservati nel browser sono presenti nel nuovo catalogo**.
I 76 riferimenti prima assenti sono stati anche scaricati e archiviati con successo.

## Modifiche

- `network.py`: ammesso `time` solo sui link pluginfile della stessa origine,
  con un singolo valore ASCII numerico di massimo 16 cifre. Parametri sconosciuti
  rifiutati anche se vuoti. Nessuna estensione ad altri host o altre route.
- Lettura `/mod/assign/view.php` limitata al solo parametro id, singolo, numerico
  positivo. POST e action=editsubmission restano vietati.
- `moodle.py::expand`: per un compito legge la pagina, conserva l'attività e aggiunge
  i file presenti in `#region-main`: materiali, consegne già caricate e feedback.
  I link duplicati vengono deduplicati e i collegamenti esterni restano esclusi.
  Un layout privo della regione principale mantiene l'attività e produce un avviso.
- Conservati corso, sezione, attività e relativo indice per i nuovi file.
- Aggiornati i test della policy che prima vietavano qualunque lettura dei compiti:
  ora verificano il divieto di scrittura e la validità degli identificativi.
- Aggiunto il verificatore referenziato dai test al MANIFEST dello sdist, così quei
  test possono essere importati anche dalla distribuzione sorgente.

Upload, consegne e nuovi tentativi quiz non sono stati implementati o eseguiti.

## Collaudo reale dopo la correzione

Nuova scansione autenticata di tutti i corsi, salvata in un workspace separato nel
progetto: **32 corsi, 279 sezioni, 642 risorse, di cui 516 file**. Prima erano 564
risorse e 438 file. L'aumento di 78 righe file comprende i 76 URL prima assenti e
due riferimenti ora associati esplicitamente all'attività di compito.

Confronto con le impronte degli URL rilevati dal browser nel registro 20:
**147 controllati, 0 assenti**. Sono quindi chiusi i 33 casi di materiali didattici,
i 40 file consegnati e i 3 feedback mancanti. Non è soltanto un test sintetico del parser.

Selezionati per il download i 76 URL prima assenti e le due pagine HTML, inclusa
quella che risultava meno aggiornata nella precedente prova:

| Prova | Esito |
|---|---|
| Prima passata | 78 scaricati, nessun codice di errore |
| Seconda passata | 76 invariati, 2 export HTML aggiornati |
| Integrità dei download | 78 file controllati, 0 problemi |
| Archivio SQLite | integrity_check=ok; 78 oggetti BLOB riletti, 0 differenze |
| Report personale PDF | Generato e aperto con pypdf: 9 pagine |

Le prove sono isolate dai download precedenti. I file e il DB del ritest sono in
`app/.verification-site-fix/`, ignorata da Git. `comparison.json` e
`download-results.json` contengono i risultati senza titoli o credenziali.

## Verifica della GUI

Aperta la finestra **FAD Downloader 0.2.0 - Catalogo aggiornato**, con i sorgenti
corretti e il nuovo catalogo precaricato. Verificati visivamente due casi reali
tramite il campo Cerca: un allegato C# con time e un allegato di un compito Python,
entrambi prima assenti, ora mostrati come righe file nella sezione corretta.
Non viene dichiarata una ricerca manuale di tutte le 642 righe: il confronto completo
dei 147 riferimenti usa il catalogo effettivamente caricato dalla GUI.

L'avvio di questa sessione usa uno script locale nell'area di verifica; non modifica
le preferenze o i download del precedente workspace. Con l'avvio ordinario, riavviare
l'app aggiornata e usare «Scansiona FAD» per aggiornare i cataloghi precedenti.

## Test e pacchetti

- Windows Python 3.14.7: **136 passati, 4 saltati**, per Tk assente e controllo POSIX.
- Linux/Xvfb e filesystem POSIX, Python 3.10.22, 3.12.15, 3.14.4:
  **140 passati su ciascuna versione**, nessuno saltato.
- Wheel installata in ambiente Linux pulito: **140 passati**.
- Ruff, Bandit, pip check e smoke/benchmark Linux superati.
- Wheel e sdist ricostruiti. Verificata corrispondenza byte per byte di tutti i
  moduli Python della wheel con i sorgenti e presenza del helper richiesto dai test
  nello sdist. Esclusi .env reali, archivi SQLite e cartelle private di verifica.
- SHA256SUMS e SHA256.json aggiornati. Il lock delle dipendenze Linux non cambia.

Corretto anche `check_windows.ps1`: PowerShell non interrompe più la build soltanto
perché Python ne scrive l'avanzamento su stderr; il codice di uscita continua a essere
verificato e un errore reale interrompe la procedura. Script completo ripetuto con
successo, inclusi build, installazione della wheel e smoke test.

## Limiti che restano

Restano i 37 avvisi già documentati: 16 materiali senza allegato riconosciuto,
20 quiz senza tentativo completato/revisionabile riconosciuto e un redirect esterno
rifiutato dalla policy. Il ritest non dimostra l'assenza di contenuti sul server
per le prime attività e non modifica i permessi FAD. Il gate generale resta NO-GO
per questi casi non classificati, mentre le omissioni accertate dal registro 20
sono chiuse con evidenza. Nessuna pubblicazione o installazione di produzione eseguita.
