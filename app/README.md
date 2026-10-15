# FAD Downloader 0.1.0

Applicazione Python per GNU/Linux con GUI italiana e CLI condivisa. Raccoglie materiali e test già svolti della FAD in una directory consultabile offline.

Il flusso completo è implementato e provato con dati sintetici. Dopo la correzione del redirect `testsession`, sono stati verificati login reale, lettura di 31 corsi e logout. Completezza della scansione delle attività ed esportazioni reali richiedono ancora un collaudo dedicato.

## Avvio nel repository su Windows

```powershell
& "C:/Users/edoardo.querio/Desktop/Materie/.venv/Scripts/python.exe" -m fad_downloader --demo
```

Rimuovere `--demo` per accedere alla FAD. `preview_gui.py` cattura una schermata e chiude automaticamente la finestra: non è il launcher.
Per avviare dall'IDE aprire `run.py` e selezionare l'interprete `.venv` del repository.

## Installazione Ubuntu

Aprire il terminale nella cartella `app`:

```bash
sudo apt update
sudo apt install python3-venv python3-tk gnome-keyring
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
fad-downloader --demo
```

La GUI richiede un desktop; la CLI funziona senza display. Il login usa il file `.env` e non richiede un portachiavi. Python minimo dichiarato 3.10; collaudo locale con Python 3.14.

## Credenziali

Compilare `app/.env`:

```dotenv
FAD_USERNAME='nomeutente'
FAD_PASSWORD='password'
```

Nell'installazione di sviluppo il file viene cercato accanto a `pyproject.toml`; nel pacchetto installato nella directory corrente. `--env-file /percorso/.env`, prima del sottocomando, sceglie un file esplicito. Lo stesso file viene usato sia per lettura sia per salvataggio. Le variabili d'ambiente `FAD_USERNAME`/`FAD_PASSWORD` e il portachiavi non vengono usati dal login; nessuna interpolazione `${...}`.

All'avvio la GUI carica username e password dal `.env`, con password mascherata. I campi possono essere modificati; dopo un accesso riuscito le credenziali usate vengono salvate automaticamente nello stesso file e riproposte al prossimo avvio. Un login rifiutato non sovrascrive le credenziali precedenti. «Carica .env» rilegge il file senza riavvio; «Dimentica password» svuota entrambe le chiavi nel file. La demo non modifica le credenziali salvate. Il salvataggio è atomico, conserva commenti e altre impostazioni e non registra i valori nei log. Se il salvataggio fallisce, l'accesso resta valido e un messaggio segnala che le credenziali non sono state conservate.

`.env` contiene la password in chiaro ed è ignorato da Git. Su Linux usare `chmod 600 .env`. Password, cookie e sesskey non vengono inseriti in cataloghi, piani o report. Non passare la password negli argomenti del comando.

## Interfaccia e flusso completo

1. Accedere: parte la scansione automatica dei corsi accessibili. Leggere gli avvisi.
2. Scegliere un workspace distinto per ogni account e per la demo.
3. Cercare e selezionare corsi, sezioni, materiali o singoli tentativi completati.
4. Configurare nomenclatura e associazioni corso/cartella.
5. Generare l'anteprima, controllare le destinazioni e scaricare.
6. Consultare il report, verificare i file e aprire l'indice raggruppato per corso.

«Scansiona FAD» aggiorna il catalogo salvato: nuovi contenuti e metadati aggiornati sono evidenziati. Risorse non più rilevate sono segnalate senza cancellare file; uno scan parziale non prova una rimozione. Catalogo, report e indice salvati sono apribili senza login.
Link e consegne non supportati restano visibili come attività del catalogo: il downloader
li segnala come non supportati e non visita tali URL. La validazione dei metadati non
amplia la policy delle richieste HTTP.

Per il tema Snap, la scansione carica anche le sezioni disponibili nel menu che non
sono presenti nell'HTML iniziale. Usa esclusivamente il frammento di lettura
`theme_snap/section`, senza eseguire JavaScript. Le sezioni vengono conservate nel catalogo,
anche quando sono vuote o non contengono file scaricabili. Sezioni omonime rimangono distinte.
Con il filtro «Tutti» sono visibili anche corsi e sezioni senza risorse; i filtri materiali/test
mostrano soltanto i gruppi corrispondenti. Se un frammento non è accessibile, la sezione
resta visibile come «Non disponibile» e la scansione lo segnala.
Rieseguire «Scansiona FAD» per aggiornare i cataloghi creati prima di questa correzione.

Modelli: `{course_id}`, `{course_name}`, `{section_index}`, `{section_name}`, `{activity_id}`, `{activity_name}`, `{quiz_id}`, `{attempt_id}`. Ogni modello produce un solo nome; le associazioni possono contenere sottocartelle. Gli allegati preservano i percorsi dichiarati dalle API o ricavati da `mod_folder`. Percorsi già assegnati prevalgono sulle nuove regole, senza rinomine implicite.

«Salva impostazioni» conserva nomenclatura e mapping nel workspace; directory, default e limiti nella configurazione globale. All'avvio le impostazioni workspace prevalgono su quelle globali. Linux: `$XDG_CONFIG_HOME/fad-downloader/settings.json`, oppure `~/.config/fad-downloader/settings.json`; Windows: `%APPDATA%/fad-downloader/settings.json`.

## Interruzioni e conflitti

«Annulla» conserva i file completati. Un file interrotto riparte da zero; niente HTTP Range. Il piano viene salvato prima del download; fallimenti e conflitti restano recuperabili. «Ritenta falliti» prepara una nuova anteprima; dopo un riavvio accedere allo stesso account e usare «Recupera piano».

È prevista una sola riautenticazione automatica per download tramite `.env`, verificando l'identità dell'account. Senza credenziali disponibili è necessario un nuovo accesso manuale.

File modificati localmente non vengono sovrascritti. «Copia conflitti» prepara destinazioni alternative e conserva la copia modificata. Gli export HTML usano generazioni: un errore conserva la precedente versione; le generazioni obsolete non vengono eliminate automaticamente.

## Backup e recupero

«Backup stato» conserva manifest, catalogo, impostazioni, piano e report in `.fad/backups`. Non include gli allegati: per proteggerli copiare l'intero workspace.

«Ripristina backup» conserva lo stato corrente, applica un backup interno e ricrea l'indice. Può recuperare un manifest JSON corrotto; rifiuta schemi futuri e account diversi riconoscibili. Lo schema 1 della 0.0.1 resta compatibile con valori predefiniti per i nuovi campi. Nessuna conversione implicita di schemi sconosciuti.

L'inventario riconosce temporanei `.part-*`; la rimozione resta manuale. Non modificare lo stato mentre l'app sta lavorando.

## CLI

```bash
fad-downloader --help
fad-downloader scan --demo --workspace "$HOME/FAD-demo"
fad-downloader plan --demo --workspace "$HOME/FAD-demo"
fad-downloader download --demo --workspace "$HOME/FAD-demo"
fad-downloader verify --workspace "$HOME/FAD-demo"
fad-downloader catalog --workspace "$HOME/FAD-demo"
fad-downloader report --workspace "$HOME/FAD-demo"
fad-downloader backup --workspace "$HOME/FAD-demo"
fad-downloader recovery --workspace "$HOME/FAD-demo"
fad-downloader restore --workspace "$HOME/FAD-demo" --backup .fad/backups/NOME_BACKUP
fad-downloader --env-file .env download --non-interactive --course-id 123 --type materials
fad-downloader download --resume --non-interactive
fad-downloader download --copy-conflicts --non-interactive
```

`plan` e `download --dry-run` non scrivono materiali o stato; una scansione reale richiede comunque rete. `scan` salva il catalogo. `--type`: all/materials/quizzes. `--workspace` prevale sulla directory globale; default `~/FAD` o `~/FAD-demo`. `--file-limit` e `--run-limit`, prima del sottocomando, regolano i byte per la CLI. In GUI usare «Limiti».

Codici: 0 riuscito, 1 errore, 2 configurazione, 3 esito parziale/problemi di verifica, 4 autenticazione richiesta, 130 interruzione da tastiera.

## Sicurezza, limiti e ambito

Origine HTTPS fissa, TLS verificato, redirect controllati, DNS privato rifiutato. Endpoint di lettura consentiti; login e logout espliciti. Nessun avvio/invio di quiz o consegne. HTML senza script, form attivi, campi nascosti e caricamenti remoti. Tipi di domanda non riconosciuti sono rifiutati; risposte, voti e feedback non visibili non vengono ricostruiti.

Gli allegati originali non vengono eseguiti e restano file non attendibili. Materiali e risultati non sono cifrati: proteggere il workspace con i permessi del proprio account.

Limiti iniziali: documenti 20 MiB, file 2 GiB, totale 10 GiB, 10.000 pagine/risorse; timeout 10 s, budget richiesta 300 s. Configurabili entro massimi validati. Richieste seriali, intervallo 250 ms, massimo 3 tentativi GET. Retry-After oltre 30 s viene segnalato per ritentare successivamente.

L'annullamento è cooperativo; DNS bloccato può ritardare la chiusura. Le protezioni filesystem presuppongono un workspace non modificabile da utenti ostili.

SSO/MFA, SCORM, forum, video esterni, script dinamici, PDF dei test e HTTP Range sono fuori dall'ambito concordato. La replica delle sottocartelle richiede percorsi esposti da Moodle. Non si garantisce compatibilità con ogni tema o plugin.

## Log e diagnostica

I log su file sono attivi per default a livello `INFO`. Il terminale mostra il percorso;
la GUI offre «Apri log». Per una diagnosi dettagliata avviare:

```powershell
& "C:/Users/edoardo.querio/Desktop/Materie/.venv/Scripts/python.exe" -m fad_downloader --log-level DEBUG
```

Oppure, su Linux: `fad-downloader --log-level DEBUG`.
`--log-dir /percorso/logs` sceglie una directory; `--no-log` disabilita la scrittura.
Queste opzioni precedono il sottocomando, per esempio `fad-downloader --log-level DEBUG download --demo`.

Directory predefinita: `%LOCALAPPDATA%/fad-downloader/logs` su Windows;
`$XDG_STATE_HOME/fad-downloader/logs` o `~/.local/state/fad-downloader/logs` su Linux.
Formato JSON Lines: una riga per evento, con ora UTC, livello, PID, thread, sessione
e identificativo dell'operazione. Ogni processo usa un proprio file per evitare
collisioni nella rotazione: massimo 5 MiB e 5 copie precedenti per processo.
I file di processi precedenti restano disponibili e possono essere archiviati o rimossi manualmente.

Copertura: avvio/uscita, GUI e worker, login/logout, disponibilità `.env`, portachiavi,
richieste e redirect, retry, scansione, pianificazione, download/export, byte trasferiti,
scritture atomiche e lock, configurazione, catalogo, piani, backup/ripristino e integrità.
`DEBUG` aggiunge dettagli di rete e filesystem; `INFO` registra esiti e tempi;
`WARNING`/`ERROR` evidenziano i problemi. Gli errori includono codice, tipo e nomi funzione/righe.

Password, username, cookie, token, valori delle query, payload, HTML, titoli dei corsi,
nomi dei materiali e percorsi di lavoro non vengono registrati. Le risorse sono identificate
da un prefisso dell'hash; la rete usa solo nomi di route conosciute e nomi di parametri consentiti.
I messaggi grezzi delle eccezioni e i log delle librerie HTTP non vengono copiati nei file.
Su Linux i nuovi file hanno permessi `600`. I log diagnostici possono essere prodotti anche
in simulazione, che continua a non scrivere materiali o stato del workspace.

## Test e build

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check src tests
python -m bandit -r src/fad_downloader
python -m build
```

Senza display Linux usare `xvfb-run -a python -m pytest -q`. I test bloccano rete e isolano configurazione globale. `check_linux.sh` e `check_release.sh` verificano Linux, build, installazione wheel, demo e dipendenze. `requirements-linux-tested.txt` registra versioni provate; non è un lock con hash.

Moduli: domain, storage, network, credentials, env_config, moodle, exporter, services, state, gui, cli, demo. Stato dei requisiti e del collaudo: [registro 0.1.0](../plan/13_VERSIONE_0_1_0.md).
