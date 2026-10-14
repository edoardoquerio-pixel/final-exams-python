# 06 - Interfaccia e flussi

## Schermate

1. Login: username/password mascherata, Accedi, Ricorda disattivato per default, cambio account/cancellazione dati salvati.
2. Prima configurazione: scan e mapping modificabile, evidenza dei risultati parziali, conferma prima del salvataggio.
3. Selezione: Treeview corsi/sezioni/attività, ricerca, filtri materiali/test, tentativi completati. Coerenza selezione parent/child.
4. Impostazioni: root, template, prefissi, separatori e cartelle; errori vicino ai campi, anteprima concreta.
5. Piano: destinazioni, collisioni, aggiornamenti da verificare, esclusioni; nessun trasferimento ancora avviato.
6. Esecuzione: progresso e contatori, log redatto, Annulla. Dimensione sconosciuta indeterminata, nessuna percentuale inventata.
7. Risultato: report, retry selezionati, apri indice/cartella.

## Flussi

- Primo avvio: login → scan → mapping → nomenclatura → selezione → anteprima → download → report.
- Avvio successivo: mappa conservata, aggiornamento a richiesta, piano nuovo.
- Sessione scaduta: attesa login → stesso account/piano → ripresa; cambio account invalida il piano.
- Annullamento: segnale worker, richiesta conclusa entro timeout, cleanup temp, report cancellato, nessun nuovo trasferimento.
- Chiusura durante lavoro: conferma annullamento, attesa cleanup senza bloccare event loop, uscita.
- Cambio regole: anteprima invalidata e nessuna rinomina implicita dei file esistenti.

## Reattività e usabilità

Tk solo nel main thread, Queue e `after()`, callback brevi. Run/account ID sugli eventi; pulsanti coerenti e doppio avvio impedito. Testare focus, tab order, tastiera, contrasto, resize, DPI e titoli lunghi. Non distinguere esiti solo col colore. Nessun traceback o segreto nei messaggi utente.

## Simulazione e CLI

Simulazione può leggere la rete, non scarica asset né scrive materiali/stato/mappa. Salvataggio esplicito impostazioni separato. GUI e CLI generano lo stesso piano dagli stessi input. Nessun prompt terminale nascosto nel worker GUI.

## Offline, conflitti e stati incompleti

Dalla schermata iniziale offrire «Apri raccolta locale» senza autenticazione. Mostrare data dell'ultimo aggiornamento: una copia locale non implica che il server sia stato ricontrollato. Indice e report non devono attivare richieste remote automatiche.

Conflitto su file modificato: mostrare percorso e motivo; permettere di saltare, salvare una nuova copia o sostituire con conferma esplicita. La sostituzione viene nuovamente verificata al commit. Una scansione parziale mostra corsi non verificati e non rimuove selezioni/mapping precedenti come se fossero assenti.

Un export parziale elenca domande/asset non disponibili. Non colorare «completato» un quiz che ha perso risposte durante il parsing. Un file rimosso dal server resta locale e viene indicato come non più verificabile, senza cancellazione.

## Dettagli operativi

Salvare la configurazione prima del download è un'azione esplicita e distinta dalla simulazione. La prima scansione salva solo quando confermata. Mostrare progresso indeterminato quando non esiste un totale affidabile; aggregare gli eventi frequenti e limitare il registro visibile, conservando gli errori.

Usare una coda limitata e messaggi di progresso sostituibili; consegnare sempre eventi terminali. Non bloccare il worker tentando indefinitamente di accodare eventi dopo la chiusura della GUI. Il tempo di annullamento effettivo deve rispettare il contratto misurato in F0A.

## Contratto CLI iniziale

`python -m fad_downloader` avvia la GUI; `--help` funziona anche senza display. Sottocomandi previsti: `scan`, `plan`, `download`, `verify`, `report`. Non importare/inizializzare Tk nei percorsi CLI. Opzioni comuni: workspace, corso/ID, selezione tipi, dry-run, output report. Password soltanto interattiva o keyring; in modalità non interattiva, credenziali assenti producono errore senza bloccare su un prompt.

Codici proposti da congelare in F1: 0 operazione completata; 1 fallimento operativo; 2 argomenti/config invalidi; 3 risultato parziale/conflitti; 4 autenticazione richiesta; 130 annullamento. Output strutturato JSON opzionale con schema documentato e senza messaggi di log su stdout. CLI e GUI condividono `ResourceResult`, non duplicano la logica.
