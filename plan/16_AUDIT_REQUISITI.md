# Audit dei requisiti — 26 ottobre 2026

Aggiornamento successivo: [collaudo produzione](18_COLLAUDO_PRODUZIONE.md).
129 test passati su ciascuna versione Linux 3.10/3.12/3.14; pagine corrette e verificate
dal vivo. Restano 16 materiali non riconosciuti. R03 è stato riallineato al contratto `.env`
già scelto dall'utente; i riferimenti seguenti al disallineamento descrivono il primo audit.

Esito: i punti funzionali richiesti sono presenti nel codice, ma **non tutti i criteri
di accettazione del piano sono chiusi**. Non confondere implementazione con collaudo finale.
Upload rimandato per istruzione dell'utente, quindi escluso dal perimetro corrente.

Audit basato sui requisiti R01–R28, sulla matrice iniziale, sul codice e sui test in `app/`,
sui registri 13/14 e sulle [verifiche eseguite](15_VERIFICHE_2026_10_26.md).
Non sono stati ripetuti test già superati senza cambiamenti al codice.
Le prove storiche restano distinte da quelle della sessione corrente.

## Lista richiesta dall'utente

| Punto | Riscontro | Limite di accettazione |
|---|---|---|
| CUI: inserimento utenza FAD | `cli.py`: username/password richiesti quando non disponibili nel `.env`; login condiviso | Login reale riuscito nei registri storici, non ripetuto oggi |
| CUI: scelta corsi | `--course-id` ripetibile | Interfaccia a sottocomandi, non menu numerico guidato |
| CUI: scelta oggetto nel corso | `--resource-id` ripetibile, filtri corso/tipo verificati da `test_cli_selects_individual_objects` | ID ricavati da scan/plan |
| Aggiornamento incrementale | `test_services.py`: file già presenti, file mancanti, hash/304, conflitti; `test_state.py`: catalogo aggiornato | Completezza sul server reale ancora da confrontare |
| GUI | `gui.py`, test dedicati e prove storiche | Tre test GUI saltati nell'ultima suite per display assente |
| DB SQLite, oggetti BLOB | `database.py`, `test_database.py`: principali/allegati, chunk, integrità, rollback e ripristino | BLOB in `object_chunks.data`, non soltanto percorsi locali |
| Almeno due utenti senza admin | `test_two_ordinary_users_password_hashes_and_login`, isolamento DB e CLI con due utenti | Account applicativi locali, distinti dagli account FAD; due utenti predefiniti solo demo |
| PDF ReportLab personale | `pdf_reports.py`, test isolamento, revoca sessione e multipagina; CLI con due utenti | Esporta un PDF; non è implementato un comando dedicato per inviarlo alla stampante fisica |
| Upload compiti | Non implementato | Rimandato, non richiesto nel perimetro attuale |

## Copertura del piano tecnico

«Prove automatiche» indica copertura dei casi presenti nella suite, non prova esaustiva.
«Parziale» indica che manca almeno una prova di accettazione o che il contratto va riallineato.

| ID | Riscontro nel codice/test | Stato e prova residua |
|---|---|---|
| R01 | GUI/CLI, packaging; prove WSL storiche | Parziale: installazione pulita e GUI desktop Linux autonomo |
| R02 | `test_moodle`, `test_network`, riautenticazione in `test_state` | Parziale: ciclo reale completo di errore/scadenza/ripresa |
| R03 | `env_config`, test lettura/salvataggio/cancellazione; isolamento account | Contratto iniziale superato: backend sicuro/consenso non descrivono il salvataggio automatico `.env` attuale |
| R04 | `test_moodle`, `test_snap_sections`, `test_catalog_policy` | Parziale: confronto completo col browser; scansione storica con avvisi |
| R05 | `test_catalog_changes_and_account_isolation`, mapping e percorsi stabili | Prove automatiche; conferma su catalogo reale residua |
| R06 | Selezione GUI e CLI, nuovo test oggetti/corsi | Parziale: GUI non rieseguita con display |
| R07 | Filtri materiali/quiz e tentativi completati | Prove automatiche; confronto contenuti reali residuo |
| R08 | `test_storage`, nomenclatura e mapping in `test_state/services` | Prove automatiche su percorsi e stabilità; usabilità reale residua |
| R09 | Cartelle Moodle, collisioni e verifica indipendente demo | Parziale: download cartelle reali e sottocartelle da confrontare |
| R10 | `test_exporter`, export demo e allegati | Parziale: completezza pagina/libro reale e navigazione manuale |
| R11 | Quiz completati, identità tentativo, paginazione e tipi sconosciuti | Parziale: fedeltà delle review reali |
| R12 | Hash, file mancante, dimensione errata, 304 e verifica indipendente | Prove automatiche; ulteriori condizioni rete reali residue |
| R13 | Piano persistente, stessa identità e una riautenticazione | Prove automatiche; scadenza reale durante download residua |
| R14 | Dry-run senza workspace, cancellazione con risultato per task, test GUI | Parziale: reattività GUI sotto carico e display disponibile |
| R15 | Report, task persistenti e recupero; conteggi separati | Parziale: collaudo del retry selettivo dalla GUI |
| R16 | Indice generato dai servizi e navigazione offline | Parziale: controllo manuale dei link su esportazioni reali |
| R17 | CLI testata, servizi comuni e selezione oggetti | Parziale: parità completa con GUI, non deducibile dalla sola condivisione servizi |
| R18 | Catalogo/report offline, comandi catalog/report e test stato | Prove automatiche; navigazione desktop Linux residua |
| R19 | File modificati preservati, copia alternativa e rimozioni non distruttive | Prove automatiche |
| R20 | `test_atomic_export_keeps_previous_generation`, scritture atomiche | Parziale: crash di processo in punti diversi non esauriti dal test di errore |
| R21 | Limiti rete e cancellazione, validazione impostazioni | Parziale: soglie temporali, DNS bloccante, rete lenta e carico non misurati |
| R22 | XDG, precedenze e CLI senza Tk; wheel storiche | Parziale: build corrente bloccata da setuptools assente; Python 3.10/3.12 non provati |
| R23 | Policy URL/DNS/redirect, blocco metodi di scrittura, HTML sanitizzato, percorsi sicuri | Parziale: prova no-follow POSIX saltata su Windows; nessuna certificazione esaustiva |
| R24 | Esiti, conteggi risorse/file e verificatore indipendente | Prove automatiche |
| R25 | Schema futuro rifiutato, backup/ripristino e temporanei | Parziale: crash nel ripristino composto; non è una transazione unica |
| R26 | BLOB principali/allegati, hash, chunk, rollback e file locale conservato su errore DB | Prove automatiche |
| R27 | Due utenti ordinari, password scrypt, sessioni e proprietà verificate | Prove automatiche; flusso GUI da rieseguire con display |
| R28 | PDF personale, multipagina, escaping e sessione revocata | Prove automatiche; verifica visiva corrente non eseguita |

## Disallineamenti da non nascondere

- R03 e la relativa riga della matrice iniziale citano keyring; il comportamento corrente
  documentato usa `.env` in chiaro con salvataggio dopo login riuscito. Non dichiarare
  soddisfatto il vecchio requisito «backend sicuro» mediante la sola presenza di test `.env`.
  Per un prossimo intervento sulle credenziali riallineare il contratto o scegliere una migrazione.
- La matrice iniziale riportava tutte le righe «da implementare» e ometteva R26–R28:
  è una mappa storica, questo audit descrive lo stato corrente.
- La compatibilità dichiarata Python 3.10+ non è interamente collaudata usando Python 3.14.7.
- «Stampa su PDF» è interpretata come generazione del report PDF, come implementato;
  l'invio a una stampante fisica sarebbe un requisito ulteriore.

## Priorità per chiudere l'accettazione

1. Ripristinare la possibilità di build in un ambiente locale al progetto e provare la wheel corrente.
2. Collaudare GUI e flussi a due utenti con display, poi Linux/POSIX e versioni Python dichiarate.
3. Confrontare in modo deliberato catalogo, materiali, pagina/libro e quiz completato con la FAD reale.
4. Misurare annullamento e limiti nelle condizioni controllate del piano, inclusi DNS/rete lenta/carico.
5. Riallineare i documenti storici sulle credenziali senza modificare silenziosamente il comportamento.

Fino alla chiusura di questi punti, l'esito corretto è «funzionalità presenti, accettazione finale parziale».
