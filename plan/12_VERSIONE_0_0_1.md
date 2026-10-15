# Versione 0.0.1 — 14 ottobre 2026

## Ambito consegnato

Implementazione nuova nella cartella `app/`, indipendente dal precedente script.
GUI Tkinter italiana e CLI condividono servizi di scansione, pianificazione, download,
export HTML e verifica. La demo offline contiene un allegato, una pagina e un quiz completato.
Istruzioni e limiti sono in [README](../app/README.md); i cambiamenti in [CHANGELOG](../app/CHANGELOG.md).

Sono implementati login Moodle, memoria facoltativa nel portachiavi, ricerca e selezione,
modelli di nomenclatura, associazioni corso/cartella, anteprima senza scrittura,
download streaming, esportazione dei tentativi revisionabili, manifest e report,
indice locale e confronto SHA-256. Il lavoro di rete avviene in un worker seriale.
Una selezione cambiata durante la pianificazione invalida l'anteprima precedente.

## Verifiche effettuate

| Verifica | Ambiente | Esito |
|---|---|---|
| `python -m pytest -q` | Windows, Python 3.14, Tk 9 | 52 passati, 1 saltato perché specifico POSIX |
| `xvfb-run -a python -m pytest -q` | Ubuntu 26.04 LTS in WSL, Python 3.14.4 | 53 passati, nessuno saltato |
| `ruff check src tests` | Ambiente di sviluppo | Nessuna segnalazione |
| `bandit -r src/fad_downloader` | Ambiente di sviluppo | Nessuna segnalazione; non sostituisce una revisione di sicurezza |
| GUI demo | Windows | Cattura osservata: campi, lista, schede e comandi leggibili |
| Build sdist e wheel | Ambiente isolato | Pacchetto 0.0.1 generato |
| Installazione wheel | Nuovo virtualenv Ubuntu | Versione corretta; download demo di 3 risorse; verifica 3 file, 0 problemi |
| Audit dipendenze runtime | Versioni installate su Ubuntu | Nessuna vulnerabilità nota rilevata alla data del controllo |

Gli script `app/check_linux.sh` e `app/check_release.sh` riproducono le prove Linux
utilizzando ambienti virtuali nella home. `app/requirements-linux-tested.txt` registra
le versioni runtime provate: non è un lock universale, né contiene hash per ogni distribuzione.
La rete è bloccata dalle fixture dei test; installazione e audit richiedono invece rete.
Il pacchetto locale non è sottoposto all'audit PyPI: è controllato dai test e dall'analisi statica.

I test coprono percorsi e link simbolici, collisioni, lock, file locali modificati,
scritture interrotte, dimensioni errate, risposta di login al posto di un file,
redirect esterni, DNS privato, richieste AJAX non autorizzate, cancellazione,
manifest corrotto, separazione account, conservazione delle vecchie generazioni,
sanitizzazione, risposte statiche dei quiz, paginazione sintetica e GUI end-to-end demo.

## Gate ancora aperti

Aggiornamento richiesto dall'utente: è supportato un file `.env` locale per le credenziali,
in aggiunta al portachiavi. Questo modifica la scelta iniziale che escludeva file plaintext;
`.env` è ignorato da Git e non deve essere inserito nelle fixture o nei materiali condivisi.
Le cifre delle verifiche sopra descrivono il collaudo iniziale, prima di questo aggiornamento.

F0A non è conclusa: lo sviluppo 0.0.1 procede come prototipo sperimentale prima delle prove
live previste nel piano. Non si dichiara alcuna fase finale interamente verificata.

- Login sulla FAD reale e confronto dei corsi/attività con il browser, con un account autorizzato.
- Completezza delle esportazioni quiz reali e compatibilità di tema, plugin e paginazione.
- Portachiavi Secret Service su una sessione desktop Linux con backend bloccato e sbloccato.
- Installazione su una distribuzione Linux desktop autonoma; WSL/Xvfb non copre tutti i comportamenti desktop.
- Compatibilità con Python 3.10 dichiarato come minimo, e matrice delle altre versioni.
- Prove di arresto forzato, race avversarie tra processi e rete lenta/instabile su infrastruttura controllata.
- Distribuzione con dipendenze bloccate e hash, verifica delle licenze e controlli CI di rilascio.

## Differenze rispetto al prodotto finale

La prima scansione richiede il pulsante dopo il login; catalogo e sessione non vengono
persistiti. Impostazioni nel workspace, caricamento esplicito e nessuna configurazione XDG globale.
Ripresa per file completati, senza Range; sessione scaduta gestita con nuovo login manuale.
Cartelle Moodle non replicate fedelmente; export quiz solo HTML con tipi riconosciuti.
Generazioni obsolete conservate; nessuna migrazione o pulizia automatica.
Annullamento cooperativo con limiti durante DNS e richieste bloccate.

## Prossimo incremento

Eseguire F0A su un corso autorizzato e registrare soltanto metadati privi di credenziali.
In base all'esito, correggere il parser Moodle e il flusso quiz prima di aggiungere nuove funzioni.
Poi introdurre persistenza del catalogo, configurazione XDG e copertura del portachiavi desktop.
