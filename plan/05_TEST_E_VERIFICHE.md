# 05 - Test e controlli ridondanti

## Livelli

Unit test puri; integrazione con server locale/filesystem temporaneo/keyring finto; test controller GUI e smoke con display Linux; prove live separate e deliberate; review del diff e degli esiti in passata distinta.

La ridondanza usa oracoli diversi. Tre test che confrontano lo stesso helper con se stesso non sono tre controlli indipendenti.

| Area | Casi obbligatori | Oracolo distinto |
|---|---|---|
| Login | Token assente, login 200 HTML, credenziali errate, timeout, sessione scaduta | Identità autenticata e pagina attesa |
| Keyring | Consenso/no consenso, assente/bloccato/plaintext, delete, cambio account | Spy metodi e segreto sentinella assente dai file |
| Scansione | >100 corsi, pagina ripetuta, API parziale, fallback, vuoto/403 | Elenco atteso scritto manualmente |
| Mapping | Titoli uguali, corso rinominato, nuove attività, regole sovrapposte | ID stabili e diff atteso |
| Percorsi | Unicode, traversal, assoluti, symlink/race, lunghezza | Root e sentinella esterna invariata |
| Download | 0 byte previsto, piccolo, grande, chunk interrotto, disco pieno | Size/hash calcolati da altro script |
| Aggiornamenti | 304 valido/invalido, ETag nuovo, URL uguale, file cancellato/corrotto | Contenuto noto del server |
| Atomicità | Crash prima/dopo rename e stato, JSON tronco | Originale o nuovo file completo, mai parziale |
| Concorrenza | Due processi, doppio click, stato condiviso, crash | Un writer e JSON consistente |
| Quiz | Tentativi multipli, review multipagina, feedback assente, 403 | Confronto manuale browser e conteggi |
| HTML | Script, onerror, SVG, iframe, CSS remoto, javascript URL | Nessuna esecuzione/richiesta in browser |
| GUI | Rete lenta, annulla, chiudi, eventi tardivi, cambio account | UI reattiva e cleanup completato |
| Report | Esiti misti, retry, annullamento, zero risorse | Conteggi e link sul disco |
| URL | HTTP, altra origine/porta, redirect 307, localhost | Server vietato non riceve richieste |

## Fault injection

Guasti su chunk, apertura file, flush/fsync, rename, salvataggio stato, AJAX e callback. Simulare ENOSPC/permessi senza riempire il disco reale. Crash con subprocess e directory temporanee. Testare conseguenze sui dati, non solo eccezioni.

## Comandi previsti

Da `app/`, dopo configurazione di package e strumenti:

```bash
python -m pytest -m 'not live' -q
python -m pytest -m 'not live' --cov=fad_downloader --cov-branch --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
python -m mypy src/fad_downloader
python -m bandit -r src/fad_downloader
python -m pip_audit
```

Configurare marker `live` e blocco della rete esterna per default. Sono comandi futuri, non verifiche già eseguite. Coverage identifica rami mancanti ma non dimostra correttezza. Failure mode critici richiedono test espliciti. Esclusioni di analizzatori motivate e registrate.

## Verificatore indipendente

Script read-only per manifest: hash/dimensioni ricalcolati, file e asset esistenti, link indice, conteggi. Non importare helper di hash del downloader. Segnalare orfani senza eliminarli né riparare lo stato automaticamente.

## Evidenze

Versione/commit, OS/Python/Tk, comando, risultato, data e fixture. Screenshot sintetici e confronto reale anonimizzato. Conservare evidenze dei fallimenti e del nuovo run dopo la correzione. «Non verificabile» resta aperto. Non registrare segreti nei run live.

## Prove aggiunte dalla revisione

| ID famiglia | Scenario | Esito richiesto |
|---|---|---|
| T01 | Installazione e versioni | Wheel in venv pulito; nessun import dalla working tree |
| T02 | Login/keyring/account | Credenziali isolate e identità confermata prima di adottare stato |
| T03 | Catalogo e mapping | Sezioni separate/lazy e pagine ripetute, limiti e risultati parziali |
| T04 | Piano/template | Percorsi deterministici, regole cambiate, nome da header diverso |
| T05 | Trasferimento e aggiornamento | Corruzione, gzip, 304 incoerente, file locale modificato e collisioni |
| T06 | Export composto | Crash in ogni fase, vecchia generazione ancora navigabile |
| T07 | Quiz statico | Valori da input visibili preservati, hidden esclusi, plugin segnalati |
| T08 | GUI/annullamento | Deadline, DNS lento, eventi tardivi, coda piena e chiusura |
| T09 | Report/offline/CLI | Conteggi per unità, link relativi, parità risultati e codici uscita |
| T10 | Confini sicurezza | Route GET mutanti bloccate, redirect/SSRF, symlink e HTML attivo |
| T11 | Stato/recupero | Schema futuro, import malformato, migrazione fallita, orfani e lock |
| T12 | Prestazioni/limiti | 1.000 attività, 10.000 record, stream enorme e HTML compresso enorme |

Gli ID sono famiglie, non test già implementati. Ogni famiglia avrà casi nominati e assert concreti. Collegare R01-R25 tramite [10_TRACCIABILITA.md](10_TRACCIABILITA.md).

## Controlli ulteriori mirati

- Confrontare review quiz prima/dopo export: numero domande e valori selezionati identici nei campi visibili, nessuna esposizione di hidden.
- Fixture che modifica un file locale dopo anteprima: il commit deve rilevare il conflitto, non sovrascriverlo.
- Rimuovere una risorsa remota e simulare scan parziale: nessun file locale cancellato.
- Tentare una seconda esecuzione sullo stesso workspace tramite symlink del percorso; lock effettivamente comune.
- Riavviare offline: indice e report apribili senza chiamare login/keyring/rete.
- Conteggi invarianti: totale task pianificati = somma esiti terminali; asset separati dalle attività logiche; retry non gonfia il report precedente.
- File trovato con hash uguale ma account diverso: nessuna adozione automatica.
- Fault injection nel salvataggio indice: download validi restano tali e indice ricostruibile.
- Verificatore indipendente con un file alterato apposta deve fallire; non basta verificarlo solo su dati validi.

## Automazione riproducibile

Usare unittest per test del dominio come da proposta, eseguibile anche tramite pytest per fixture, marker e coverage. Definire in F1 un solo comando/script locale che orchestra le verifiche; la pipeline CI futura usa lo stesso script su Linux senza segreti. Eseguire il set completo prima del rilascio e test mirati durante lo sviluppo.

Audit dipendenze richiede rete e resta uno step distinto dai test offline; un servizio audit indisponibile è «non eseguito», non successo. Il set automatico non include la piattaforma FAD. Il job Linux verifica Python minimo e versione di riferimento; keyring reale e desktop restano collaudi manuali tracciati.
