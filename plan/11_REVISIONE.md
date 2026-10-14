# 11 - Revisione di completezza del piano

Data: 14 ottobre 2026. Revisione documentale 1.1.

## Esito

Il piano iniziale copriva le funzionalità principali, ma non era ancora sufficientemente preciso per uno sviluppo autonomo affidabile: mancavano contratti di conflitto/recupero e alcuni controlli potevano compromettere i requisiti stessi. La revisione rende espliciti questi punti e collega tutti i requisiti a test e fasi. Non è possibile garantire di avere anticipato ogni caso: restano verifiche concrete sul Moodle reale, desktop Linux e librerie scelte.

Sono stati riletti tutti i 10 documenti iniziali e confrontati con il testo sorgente della proposta. Nessun codice applicativo sviluppato o test live eseguito in questa revisione. PDF non modificato: rimane la proposta sintetica, mentre i dettagli operativi sono qui.

## Risultati della revisione

| Priorità | Lacuna o contraddizione iniziale | Correzione nel piano | Verifica ancora richiesta |
|---|---|---|---|
| Alta | Rimozione form poteva cancellare le risposte quiz | Modello statico prima della sanitizzazione; hidden esclusi | T07 e review reale |
| Alta | Atomicità descritta solo per singolo file | Export per generazioni con HTML e asset verificati | Crash test T06 |
| Alta | Hash diverso non distingueva corruzione da modifica dell'utente | Conflitto conservativo e ricontrollo al commit | T05 |
| Alta | Solo metodo HTTP/origine non garantivano sola lettura | Policy route/azioni, GET mutanti rifiutati | T10 e log richieste sintetiche |
| Alta | Timeout interpretati come limite totale di cancellazione | Budget distinto e probe DNS/socket; modello worker da validare | F0A/T08 |
| Alta | Prove live previste troppo avanti | F0A anticipa login, quiz, Linux/keyring | F0A |
| Media | Stato separato ma workspace condivisibile tra account | Workspace vincolato a origine/account e ID confermato | T02/T11 |
| Media | Anteprima e Content-Disposition potevano divergere | Percorso pianificato stabile, nome originale solo metadato | T04/T05 |
| Media | Nessuna policy per risorse sparite o file esistenti | Conservazione locale, nessun mirror distruttivo | T03/T05 |
| Media | Lock, recupero e schema non abbastanza definiti | Lock reale, migrazioni validate, staging identificato | T11 |
| Media | Mancavano soglie e prove di scalabilità | Budget iniziali e dataset di carico | T12 |
| Media | Percorsi Linux e packaging poco specifici | XDG, matrice Python, wheel in ambiente pulito | T01 |
| Media | Consultazione offline non esplicita nella GUI | Apertura raccolta senza login | T09 |
| Media | Contatori potevano mescolare file, asset e attività | Unità distinte e un esito terminale per task | T09 |
| Media | Manca relazione requisito/test/fase | Matrice R01-R25 e famiglie T01-T12 | Controllo documentale e future evidenze |
| Bassa | unittest nella proposta, pytest nel piano | unittest per dominio, pytest come runner/tooling | F1 |
| Bassa | «CLI facoltativa» ambiguo | Facoltativa nell'uso, prevista nella consegna | F10 |

«Correzione nel piano» significa requisito documentato, non problema software già risolto.

## Punti da risolvere prima dell'implementazione completa

1. Capacità reali della FAD: login, paginazione, revisione quiz e tipi domanda disponibili.
2. Matrice Linux/Python/Tk e portachiavi effettivamente utilizzabile.
3. Componente di sanitizzazione: scelta mantenuta, configurazione e test; BeautifulSoup da solo non è un sanitizer.
4. Annullamento con Requests e thread: misurare DNS/socket, scegliere eventuale processo isolato se il requisito non è raggiungibile.
5. Implementazione di trasporto sicuro, lock e aperture filesystem da dimostrare con prove avverse.

Il registro 09 assegna queste decisioni a gate precisi. Non serve deciderle tutte con l'utente: sono scelte tecniche da documentare; accesso non disponibile e variazioni di ambito richiedono invece chiarimento.

## Migliorie che non diventano requisiti ora

Download paralleli, scheduler, auto-update applicazione, resume HTTP Range, archivio versioni illimitato, supporto universale SSO e plugin Moodle: rimandati. Aumenterebbero superficie di errore e lavoro senza essere necessari alla proposta. Il progetto resta un'app desktop con una richiesta di rete per volta.

## Riscontri su fonti primarie

- Requests distingue timeout di lettura dal tempo totale del trasferimento: per questo il piano richiede una misura separata dell'annullamento e non assume che il solo parametro timeout basti. [Documentazione Requests](https://requests.readthedocs.io/en/stable/user/quickstart/#timeouts).
- Moodle rende configurabili le informazioni visibili in revisione dei quiz: l'export deve rappresentare i dati effettivamente accessibili, senza promettere risposte e feedback sempre presenti. La documentazione non identifica la versione installata presso la scuola. [Moodle: review options](https://docs.moodle.org/500/en/Quiz_settings#Review_options).
- La specifica XDG distingue configurazione e stato e richiede percorsi assoluti nelle variabili: è il riferimento per la collocazione dei dati utente. [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/).
- Tkinter richiede callback brevi per mantenere l'event loop reattivo; la scelta main thread più coda è una decisione progettuale coerente con questo limite. [Tkinter: threading model](https://docs.python.org/3/library/tkinter.html#threading-model).

## Criterio finale di completezza

Completezza documentale: requisito, contratto, componente, fase e test associati; nessun comportamento critico lasciato a interpretazione silenziosa. Completezza del prodotto: quelle prove devono poi passare sugli ambienti dichiarati. La prima è stata revisionata; la seconda resta da dimostrare durante lo sviluppo.
