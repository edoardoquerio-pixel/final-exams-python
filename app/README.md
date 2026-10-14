# FAD Downloader 0.0.1

Prima versione sperimentale del progetto di Edoardo Querio Gianetto, ITS-ICT Piemonte.
Applicazione Python per GNU/Linux, con interfaccia grafica in italiano e comandi da terminale.
La demo funziona senza connessione e senza credenziali. L'adattatore Moodle deve ancora
essere collaudato sulla FAD della scuola: i test sintetici non garantiscono la compatibilità
con il tema, i plugin e le impostazioni del sito reale.

## Installazione su Ubuntu

Aprire il terminale in questa cartella (`app`):

```bash
sudo apt update
sudo apt install python3-venv python3-tk gnome-keyring
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
fad-downloader --demo
```

Per l'accesso reale: `fad-downloader`. È necessario un desktop grafico per la GUI.
Il portachiavi Secret Service deve essere disponibile e sbloccato nella sessione desktop.
Se non è disponibile, si può accedere senza memorizzare la password.
Non vengono accettati backend che salvano le credenziali in chiaro.
Python minimo dichiarato: 3.10; ambiente effettivamente provato: Python 3.14 su Ubuntu WSL e Windows.

## Uso della GUI

1. Inserire username e password. «Ricorda» è facoltativo; salva nel portachiavi di sistema.
2. Premere «Scansiona FAD» per elencare corsi e attività accessibili. Leggere gli avvisi nella scheda messaggi.
3. Scegliere la directory di lavoro; selezionare corsi, sezioni o singole attività.
4. Impostare i nomi delle cartelle e, se necessario, associare un corso a una cartella relativa.
5. Generare l'anteprima e controllare le destinazioni, poi avviare il download.
6. Verificare i file e aprire l'indice locale. «Riprova falliti» prepara una nuova anteprima delle risorse da ritentare.

La scansione si avvia esplicitamente dopo il login, anche al primo utilizzo.
I modelli disponibili sono `{course_id}`, `{course_name}` e `{section_name}`;
le cartelle già registrate non vengono rinominate automaticamente.
«Salva impostazioni» conserva la nomenclatura nel workspace; «Carica impostazioni» la ripristina.
Usare una directory distinta per ciascun account e per la demo.
Logout chiude la sessione locale; «Dimentica» rimuove la credenziale del nome utente indicato.

## Terminale

```bash
fad-downloader --help
fad-downloader plan --demo --workspace "$HOME/FAD-demo"
fad-downloader download --demo --workspace "$HOME/FAD-demo"
fad-downloader verify --workspace "$HOME/FAD-demo"
fad-downloader report --workspace "$HOME/FAD-demo"
fad-downloader scan --username NOMEUTENTE
fad-downloader download --username NOMEUTENTE --course-id 123 --type materials --workspace "$HOME/FAD"
```

La password viene richiesta senza eco, oppure recuperata dal portachiavi; non va passata
come argomento. `--non-interactive` richiede una credenziale già memorizzata.
`download --dry-run` mostra le destinazioni senza scaricare. La scansione reale richiede comunque rete e login.
Codici di uscita: 0 riuscito, 1 errore, 2 configurazione, 3 esito parziale o problemi di verifica,
4 autenticazione richiesta, 130 interruzione da tastiera.

## Cosa comprende

- Login Moodle, salvataggio facoltativo delle credenziali, scansione corsi e sezioni.
- Ricerca, selezione, anteprima, nomenclatura personalizzabile e associazione corso/cartella.
- Download in streaming degli allegati individuati; esportazione HTML locale di pagine e libri.
- Esportazione dei tentativi quiz completati e revisionabili, limitata ai tipi di domanda riconosciuti.
- Manifest JSON, hash SHA-256, report, indice locale e verifica indipendente dei file.
- Worker per mantenere reattiva la GUI, annullamento e possibilità di riprovare gli errori.
- Scritture atomiche, lock del workspace e protezione dei file modificati dall'utente.

## Limiti della 0.0.1

Non sono ancora verificati login reale, SSO/MFA, portachiavi su desktop Linux e completezza
della scansione sul Moodle della scuola. Il fallback HTML segnala la possibile incompletezza.
Non vengono svolti né inviati test; si esporta solo quanto già disponibile in revisione.
Tipi di domanda non riconosciuti vengono rifiutati, senza dichiarare completo un export parziale.
Non sono inclusi SCORM, video esterni, contenuti dinamici, esportazione PDF dei quiz,
replica fedele delle sottocartelle Moodle, migrazioni di vecchi manifest o pulizia delle generazioni obsolete.
La riscan­sione è manuale; il catalogo non è ancora persistito. La configurazione è locale al workspace.
Un file interrotto riparte dall'inizio; i file completati restano registrati. Non è previsto HTTP Range.
Gli export HTML creano nuove generazioni anche se il contenuto non cambia.
La scadenza della sessione richiede un nuovo login e una nuova scansione.
L'annullamento è cooperativo: una risoluzione DNS bloccata può ritardare la chiusura.

## Sicurezza e dati locali

Le richieste sono limitate all'origine HTTPS della FAD e a percorsi di lettura previsti.
Redirect esterni e indirizzi di rete privati vengono rifiutati; la verifica TLS resta attiva.
Le pagine esportate vengono ripulite da script, form attivi, campi nascosti e riferimenti remoti.
Gli allegati originali restano file non attendibili: l'applicazione non li esegue.
Password e cookie non vengono scritti nel workspace. I materiali e i risultati locali non sono cifrati:
la directory va protetta con i permessi del proprio account. Non condividere workspace o report contenenti dati personali.
Le protezioni del filesystem sono pensate per un workspace posseduto dall'utente, non per una directory
modificabile contemporaneamente da utenti ostili. Prima di modifiche manuali, chiudere l'app e fare una copia.

## Sviluppo e verifiche

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check src tests
python -m bandit -r src/fad_downloader
python -m build
```

Su Linux senza display: `sudo apt install xvfb`, quindi `xvfb-run -a python -m pytest -q`.
I test bloccano la rete e usano dati sintetici. Un test GUI viene saltato se manca il display;
il test dei link simbolici POSIX viene saltato su Windows.
L'organizzazione segue i moduli `domain`, `storage`, `network`, `credentials`, `moodle`,
`exporter`, `services`, `gui`, `cli` e `demo`. GUI e CLI condividono gli stessi servizi.
Lo stato di collaudo e le attività successive sono nel [registro di versione](../plan/12_VERSIONE_0_0_1.md).
