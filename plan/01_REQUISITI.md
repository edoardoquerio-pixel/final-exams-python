# 01 - Requisiti e criteri di accettazione

| ID | Requisito | Evidenza minima |
|---|---|---|
| R01 | Avvio GNU/Linux | Installazione pulita Ubuntu e apertura GUI |
| R02 | Login, logout, sessione scaduta | Login valido/errato, timeout, nuovo accesso |
| R03 | Credenziali FAD nel `.env` e cambio account | Lettura autorevole dal file, GUI mascherata, salvataggio dopo login riuscito, cancellazione e account isolati |
| R04 | Prima scansione FAD | Corsi paginati, sezioni e attività senza duplicati |
| R05 | Mapping e aggiornamento | Scelte conservate; nuovi contenuti evidenziati |
| R06 | Selezione e ricerca | Solo corsi/sezioni/attività selezionati nel piano |
| R07 | Materiali, test o entrambi | Filtri verificati nel risultato |
| R08 | Nomenclatura configurabile | Anteprima coincide con output; percorsi invalidi rifiutati |
| R09 | Download file e cartelle | Sottocartelle preservate, collisioni risolte, file piccoli validi |
| R10 | Pagine e libri HTML | Capitoli e allegati accessibili raccolti; link locali validi |
| R11 | Test svolti | Tutti o singoli tentativi completati; review multipagina |
| R12 | Integrità e aggiornamenti | Hash, dimensione, 304, file locale mancante/corrotto, URL invariato |
| R13 | Ripresa dopo sessione scaduta | Piano conservato, nessuna contaminazione tra account |
| R14 | GUI, annullamento, simulazione | Finestra reattiva; nessuna scrittura materiali/stato in simulazione |
| R15 | Report e retry | Conteggi riconciliati; ritentati solo i fallimenti selezionati |
| R16 | Indice HTML | Collegamenti verso file esistenti e raggruppamento per corso |
| R17 | CLI facoltativa | Parità dei risultati con GUI; codici di uscita documentati |
| R18 | Consultazione offline | Indice e report già salvati apribili senza login o rete |
| R19 | Conflitti locali e contenuti rimossi | File modificati preservati; assenza remota non causa cancellazioni |
| R20 | Export coerente di pagina/libro/quiz | Aggiornamento interrotto non rompe la precedente esportazione |
| R21 | Limiti e annullamento misurabili | Trasferimento lento, risposta enorme e attesa retry interrompibili |
| R22 | Configurazione e installazione Linux | XDG, precedenza impostazioni, wheel pulito e nessun display per CLI |
| R23 | Input non fidati e sola lettura remota | Endpoint consentiti, HTML inattivo e nessuna scrittura esterna alla root |
| R24 | Risultati verificabili | Esiti tipizzati, unità di conteggio separate, manifest indipendente |
| R25 | Migrazione e recupero locale | Schema futuro rifiutato, backup ripristinabile, temporanei riconosciuti |
| R26 | Archivio SQLite dei contenuti | File principali e allegati conservati come BLOB con hash e dimensione; rollback se incompleti |
| R27 | Almeno due utenti DB ordinari | Registrazione/login, nessun ruolo admin; storico e BLOB separati per proprietario |
| R28 | Report PDF personale con ReportLab | PDF generato dal DB per l'utente connesso, senza dati di altri utenti, anche multipagina |

## Vincoli

R03 è riallineato al 26 ottobre 2026 alla scelta dell'utente già registrata nel documento 13:
login tramite `.env`, senza portachiavi o override delle variabili d'ambiente. Il file contiene
credenziali in chiaro e va protetto dai permessi del sistema; non è un archivio cifrato.
Un login fallito non sovrascrive i dati precedenti. Le indicazioni keyring del piano iniziale sono storiche.

Python 3.10+ come da proposta: Python 3.12 sarà la versione di riferimento iniziale del progetto; il limite minimo 3.10 richiede un job di compatibilità dedicato. La matrice precisa OS e versioni verrà congelata in F0. Non dichiarare compatibilità con ogni versione futura. Nessun riferimento a codice già sviluppato come prerequisito.

Quiz: soltanto tentativi completati e accessibili in revisione. Domande, risposte, risultati e feedback non visibili sono «non disponibili», mai ricostruiti o aggirati. Nessun tentativo nuovo, invio o modifica risposte. MFA/SSO non supportati si segnalano senza bypass.

Forum, video esterni e contenuti dinamici non sono parte del sito offline. HTML sanitizzato, senza garanzia di eseguire gli script originali.

## Nomenclatura

Template proposti: `{course_id}_{course_name}`, `{section_index}_{section_name}`, `{activity_id}_{activity_name}`, `quiz_{quiz_id}/attempt_{attempt_id}_{date}`. Solo segnaposto consentiti: niente espressioni Python o interpolazione arbitraria. Prefissi e separatori configurabili. ID stabili distinguono titoli uguali e rinomine.

Cambiare regole non rinomina né elimina automaticamente file preesistenti. Anteprima invalidata dopo ogni modifica alle regole.

## Completezza

Distinguere scansione completa, parziale, vuota ed errore. Un errore HTTP o di parsing non diventa una lista vuota di successo. Un corso non accessibile non blocca gli altri, ma rende il report parziale. Registrare anche attività non supportate.

## Contratti che evitano ambiguità

- La CLI è facoltativa nell'uso, ma R17 resta una consegna prevista; non è una funzione da omettere senza decisione.
- «Ripresa» significa ripartire dai file completati. Il file interrotto riparte da zero: ripresa HTTP Range fuori ambito iniziale.
- File locale diverso dall'hash registrato: conflitto, conservazione della copia locale e scelta tra percorso alternativo o sostituzione esplicita. Il solo comando di download forzato non autorizza a distruggere modifiche locali.
- Risorsa prima visibile e ora assente/inaccessibile: conservare la copia e segnalarne l'ultima verifica; non dedurre una cancellazione da uno scan parziale. Niente mirror distruttivo.
- Titolo cambiato, nuova scansione o template cambiato: l'identità resta stabile; il percorso già assegnato prevale per le risorse registrate. Nuove regole solo per nuove risorse. Un cambio root crea un nuovo workspace e non sposta dati implicitamente.
- L'anteprima mostra i percorsi assegnati. Se il server rivela un nome diverso solo durante il trasferimento, mantenere il nome pianificato e registrare l'originale come metadato; non cambiare destinazione in silenzio.
- Annullamento conserva i file completati, marca i task non avviati come annullati e permette una nuova pianificazione. Non è una promessa di pausa/ripresa del singolo stream.
- Login e download richiedono rete; lettura di indice, report e materiali già presenti no.
- Separazione account nell'app e nei manifest non cifra i file scaricati: l'accesso locale dipende dai permessi dell'utente GNU/Linux.

## Soglie iniziali da collaudare

Una sola richiesta in volo; intervallo minimo iniziale 250 ms tra richieste; massimo 3 tentativi complessivi per GET ripetibile, 5 redirect e una riautenticazione automatica per run. Timeout connessione 10 s, inattività di lettura 10 s, budget per richiesta 300 s. Retry-After rispettato entro il budget, altrimenti task differito e segnalato.

Limiti iniziali configurabili con validazione: HTML/JSON decodificato 20 MiB, file 2 GiB, totale per run 10 GiB, massimo 10.000 pagine/task visitati. Raggiungere il limite produce un risultato parziale esplicito. Nessuna espansione automatica dei limiti.

Con 1.000 attività e 10.000 record locali: obiettivo risposta comandi UI entro 200 ms, nessuna coda eventi senza limite e download a memoria indipendente dalla dimensione del file. Obiettivo annullamento: nessun nuovo task dopo il segnale, completamento entro 15 s nelle condizioni di rete controllate; DNS e librerie bloccanti vanno misurati in F0. Se il modello thread non soddisfa l'obiettivo, rivederlo prima di promettere questa garanzia.
