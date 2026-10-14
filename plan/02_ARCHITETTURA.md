# 02 - Architettura e dati

## Struttura proposta

```text
app/
  pyproject.toml
  README.md
  src/fad_downloader/
    __init__.py
    __main__.py
    domain/       # modelli senza rete o GUI
    services/     # scansione, piano, download, export, report
    adapters/     # HTTP, Moodle, keyring, JSON
    gui/          # finestre, controller, eventi
    cli/          # comandi alternativi
    security/     # URL, percorsi, HTML, log
  tests/
    unit/
    integration/
    gui/
    fixtures/     # sintetiche o anonimizzate
  docs/
  scripts/
```

Dipendenze verso il dominio, mai verso la GUI. Servizi con HTTP, clock, filesystem e credenziali sostituibili nei test. Nessun effetto collaterale al momento dell'importazione.

## Modelli e identità

- AccountContext: origine Moodle e account, senza password serializzabile.
- Course/Section/Activity: ID, titolo, tipo, posizione, accessibilità.
- Resource: identità stabile, URL operativo, percorso relativo, dimensione attesa facoltativa.
- QuizAttempt: quiz ID, attempt ID, data con timezone, stato completato, campi visibili.
- DownloadPlan: snapshot di selezione, destinazioni e versione delle regole.
- DownloadRecord: percorso, dimensione, SHA-256, validatori HTTP, data UTC, dipendenze.
- RunReport: eventi ed esiti senza URL contenenti segreti.

Identità composta da origine/account/corso/attività/risorsa o tentativo. Non basarla sul titolo. Canonicalizzazione per deduplica separata dall'URL effettivo, che mantiene i parametri necessari.

## Persistenza

JSON distinti e versionati per configurazione, mapping, stato e report. Password nel portachiavi. Stato separato per account. Cambio account chiude sessione HTTP e invalida il piano.

Temp nella stessa directory, flush/fsync, rename atomico; sincronizzazione directory su Linux dove supportata. Stato registrato dopo il file completo. Crash tra file e stato: orfano da verificare prima di adottarlo, senza sovrascriverlo. Backup prima delle migrazioni. Stato corrotto: errore esplicito, nessun azzeramento automatico.

## Concorrenza e stati

Worker rete seriale iniziale con sessione di sua proprietà. Tkinter soltanto nel main thread; Queue e `after()` per eventi. Eventi con run ID/account ID, ignorando quelli tardivi. Cancellazione cooperativa con timeout, nessuna terminazione forzata del thread.

Lock del sistema operativo sulla directory di lavoro, rilasciato alla morte del processo. Bloccare anche stati condivisi tra output diversi. Filesystem di rete supportati solo dopo verifica.

Esecuzione: idle → authenticating → scanning → ready → downloading → completed/partial/failed/cancelled. Sessione scaduta: awaiting_login con limite ai tentativi.

Risorsa: discovered → planned → transferring → validated → committed → recorded. Prima del commit nessun errore può modificare la copia definitiva. Esiti: scaricato, aggiornato, invariato, fallito, non accessibile, non supportato.

## Contratti dei componenti

| Componente | Input / output | Responsabilità |
|---|---|---|
| AuthService | credenziali temporanee → AccountContext confermato | Identità verificata, sessione, logout |
| CatalogAdapter | account + scope → CatalogSnapshot | Capability, pagine visitate, completezza e problemi |
| Planner | catalogo + selezione + regole + manifest → DownloadPlan | Destinazioni deterministiche, conflitti, esclusioni |
| TransferService | task + cancel token → ResourceResult | Policy URL, streaming, validazione, commit |
| ExportService | contenuto accessibile → ExportBundle | Snapshot statico, asset, riferimenti, disponibilità |
| StateRepository | record versionati → checkpoint | Lock, schema, salvataggio e recupero |
| ReportService | eventi/task finali → report e indice | Riconciliazione, link relativi, nessun segreto |

`CatalogSnapshot` include ID scansione, account, istante UTC, scope richiesto, completezza per corso e motivi. `ExportBundle` include ID generazione, file entrypoint, asset con hash, disponibilità dei campi quiz e problemi. Per dati sconosciuti usare null/stato tipizzato, non stringhe vuote o valori inventati.

## Configurazione GNU/Linux

Config utente in `$XDG_CONFIG_HOME/fad-downloader` (fallback `~/.config/fad-downloader`); log/stato UI in `$XDG_STATE_HOME/fad-downloader` (fallback `~/.local/state/fad-downloader`). Ignorare variabili XDG relative. Il workspace scelto contiene `.fad/` con manifest e mapping portabili. Nessun dato scritto accanto al package installato.

Precedenza: default → config utente → config workspace → argomenti CLI/opzioni del run. La GUI rende esplicito quale livello salva. `.env` solo selezionato esplicitamente e solo per impostazioni non segrete, senza ricerca automatica nelle directory superiori.

Ogni workspace appartiene a una coppia origine/account confermata: bloccare un altro account o proporre una directory separata. Usare ID utente Moodle quando disponibile, altrimenti identità confermata e limite documentato. Alias di username non devono creare adozioni incrociate. Percorsi relativi al workspace; URL con token solo in memoria, non nei JSON.

## Pubblicazione degli export

Un export comprende HTML e asset: rename del solo HTML non basta. Preparare una generazione in staging dentro il workspace, completare asset e link e poi pubblicare un riferimento alla nuova generazione con operazione atomica. Se la verifica fallisce, la generazione precedente resta attiva. L'indice segue solo generazioni committed; un fallimento dell'indice non invalida i download e sarà riparabile al prossimo avvio.

Per aggiornare file semplici verificare nuovamente che la copia locale non sia stata modificata dopo l'anteprima. Nessuna sostituzione se l'hash/stat sono cambiati. Un manifest con checksum non prova autenticità se un processo dello stesso utente può modificarlo: il controllo protegge da corruzioni e divergenze, non da OS compromesso.

## Recupero e limiti dello stato

Schema con versioni supportate, campi obbligatori, range numerici e dimensione JSON massima. Versione futura rifiutata in scrittura. Migrazione su copia, verifica e commit, con rollback e backup precedente. Recovery individua solo temporanei appartenenti all'app tramite manifest di staging; propone cleanup dopo aver escluso processi attivi. Nessuna cancellazione generica di file `.tmp`.

JSON può richiedere riscritture costose: misurare 10.000 record in F6. Se il checkpoint per file supera i budget, valutare journal append-only o SQLite con una decisione documentata, migrazione e gli stessi invarianti di integrità.

## Risultati ed errori

`ResourceResult` distingue completato, invariato, aggiornato, fallito, non accessibile, non supportato, conflitto, annullato e parziale. Codici errore: AUTH_REQUIRED, ACCESS_DENIED, NETWORK, RATE_LIMITED, PARSE_UNSUPPORTED, INVALID_CONTENT, LOCAL_CONFLICT, IO_ERROR, LIMIT_REACHED, STATE_ERROR. Ogni errore indica se il retry è ammesso.

Conteggiare separatamente attività logiche, task di trasferimento e asset: non sommare un HTML e le sue immagini come più attività. Ogni task pianificato ha esattamente un esito terminale, anche se annullato; un nuovo retry ha run ID distinto e riferimento al precedente.
