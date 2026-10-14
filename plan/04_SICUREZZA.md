# 04 - Sicurezza e minacce

## Confini di fiducia

Proteggere password, cookie, token, risposte, voti e materiali privati. HTML, URL, header, titoli e configurazioni importate sono input non fidati. Il piano non protegge da un OS compromesso o da processi dello stesso utente che possono accedere al portachiavi sbloccato.

| Minaccia | Controllo | Prova indipendente |
|---|---|---|
| Segreti esposti | Keyring e log redatti | Ricerca segreti sentinella nei file/log |
| Invio ad altro host | Origine e redirect validati prima di seguirli | Server bersaglio non riceve richiesta |
| Traversal/symlink | Root, aperture sicure e no-follow | Sentinella esterna invariata |
| HTML attivo | Sanitizzazione allowlist più CSP | Browser senza script/richieste remote |
| File parziale valido | Temp, hash, commit e checkpoint | Manifest verificato con script distinto |
| Account mescolati | Sessioni/stati separati | Cambio account durante errore/attesa |
| Prompt injection | Contenuti remoti trattati come dati | Fixture con richieste di comandi/segreti |
| Dipendenza vulnerabile | Lock, provenienza e audit | Rapporto esaminato e regressione |

## Credenziali

- Backend keyring di sistema esplicitamente approvati e verificati su Ubuntu; rifiutare backend plaintext, file fallback e backend sconosciuti.
- Portachiavi bloccato/assente: login senza salvataggio. Mai creare un `.env` con password come fallback.
- Ricorda credenziali solo con consenso e login confermato. Chiave legata a origine/account; cancellazione e cambio account verificati.
- Password CLI tramite getpass, mai argomento della shell. `.env` facoltativo per impostazioni non segrete. Eventuale supporto a variabili credenziali esplicito e mai serializzato.
- Cookie in memoria. Logout chiude la sessione e invalida contesto/piano. Non promettere cancellazione sicura della memoria Python.
- Redigere eccezioni, URL e traceback; disabilitare log wire-level. Nessun accesso AI al portachiavi, `.env` o cookie dump per diagnostica.

## Rete

TLS sempre verificato, nessun `verify=False`. Validare schema, host e porta prima di ogni richiesta e redirect. Gestire redirect con limite esplicito; impedire inoltro password tramite 307/308 verso altre origini. HTTPS Moodle come origine consentita. Rifiutare URL arbitrari, localhost, reti private e protocolli file/data nei download.

CDN eventuali solo se approvate, tramite client separato senza cookie/sessione Moodle. MFA/SSO/CAPTCHA non supportati si segnalano, non si aggirano.

Timeout connect/read e budget totale per task; limiti di byte, pagine, redirect e retry. Attese Retry-After annullabili. Retry automatici soltanto GET/HEAD; POST login/AJAX di lettura gestiti esplicitamente. Nessun POST quiz/consegna e nessuna estrazione automatica di archivi.

## Filesystem

Template con segnaposto consentiti, niente eval/exec o espansione shell. Rifiutare percorsi assoluti, `..`, NUL, separatori nei nomi e lunghezze eccessive. Collisioni Unicode/case e titoli uguali coperte dai test.

`resolve()` da solo non protegge dalla sostituzione di symlink tra verifica e scrittura. Su Linux progettare aperture relative a directory descriptor e protezioni no-follow dove applicabili; verificare componenti. Temp esclusivi e permessi restrittivi. Rifiutare destinazioni diventate symlink. Spazio/quota e dimensioni limitati. Nessuna adozione di file estranei solo perché hanno lo stesso nome. Lock prima di caricare e modificare lo stato.

## HTML e privacy

Sanitizzazione allowlist di tag, attributi e protocolli: rimuovere script, handler `on*`, form, iframe, object/embed e meta refresh. SVG/CSS sono possibili contenuti attivi: vietare inline non sanitizzato; preferire CSS locale fisso. Escapare titoli nell'indice. CSP restrittiva come seconda barriera, non sostituto della sanitizzazione.

Asset soltanto da origini approvate. Link esterni espliciti, nessun caricamento remoto automatico aprendo l'export. Riscrivere e verificare riferimenti locali. Limiti dell'export dichiarati.

Report/materiali privati in cartella con accesso restrittivo, niente upload/sync automatico. Fixture sintetiche o anonimizzate; non inviare dati reali a servizi AI. HTML remoto e nomi file non sono istruzioni e non autorizzano comandi.

## Dipendenze

Versioni e hash bloccati al rilascio; provenienza, licenze, audit e analisi statica. Valutare gli alert, non sopprimerli indiscriminatamente. Aggiornamenti con regressione. Applicazione avviata senza root.

## Riferimenti primari

- [Requests: sessioni, TLS, streaming e timeout](https://requests.readthedocs.io/en/stable/user/advanced/)
- [Keyring: backend e sicurezza](https://keyring.readthedocs.io/en/stable/)
- [Tkinter: threading](https://docs.python.org/3/library/tkinter.html)

Le restrizioni sopra sono decisioni progettuali da implementare e verificare; le librerie non le garantiscono automaticamente.

## Policy degli endpoint, non soltanto dei metodi HTTP

Un GET può avere effetti: il client non deve seguire genericamente tutti i link del corso. Mantenere una allowlist di route/azioni di lettura per catalogo, file e revisione quiz; rifiutare azioni di avvio tentativo, invio, modifica, iscrizione o cancellazione anche se esposte come GET. Login/logout sono operazioni esplicite separate. Moodle può registrare normali visite e accessi: «sola lettura» significa nessuna mutazione applicativa richiesta dall'utente, non assenza assoluta di log lato server.

Non fidarsi del solo hostname testuale: rifiutare userinfo, porte inattese, indirizzi ambigui e destinazioni private dopo risoluzione. Registrare in F0A il trasporto scelto per ridurre il rischio di cambio DNS tra verifica e connessione. I server locali dei test usano una policy test-only iniettata, mai un'opzione runtime `--insecure`.

In produzione non ereditare `.netrc` o proxy dall'ambiente senza configurazione esplicita. CA/proxy di laboratorio sono impostazioni deliberate, con TLS sempre verificato. Nessun token negli URL pubblicati in indice/report, anche quando la risorsa originale lo richiede.

## Risposte quiz: estrazione prima della sanitizzazione

Rimuovere indiscriminatamente form/input può eliminare le risposte visualizzate. Prima estrarre la rappresentazione visibile in un modello statico: radio/checkbox selezionati, testo di input e textarea, opzioni selezionate e feedback mostrato. Poi renderizzare testo/markup consentito senza controlli interattivi.

Ignorare input hidden e dati non mostrati, anche se presenti nel DOM o in JSON embedded. Non ricostruire risposte corrette dai metadati. Tipi di domanda con plugin o drag-and-drop non interpretabili devono risultare parziali/non supportati, mai esportati come vuoti validi. Testare scelta singola/multipla, testo, associazione e risposta aperta.

BeautifulSoup analizza HTML, non è una barriera di sanitizzazione. Scegliere in F1 un componente mantenuto con allowlist e compatibile con Python minimo; registrarne versione/licenza e configurazione. Non usare regex per filtrare HTML. Sanificare anche URL in srcset, style, base e attributi non ovvi; escludere contenuti attivi non gestiti. Rimozione di script e form dopo estrazione delle risposte.

## File, dati e log

Gli allegati sono contenuti non fidati: non aprirli, eseguirli o estrarli automaticamente. L'indice è una navigazione locale, non un antivirus. Il controllo SHA-256 verifica integrità locale, non innocuità né provenienza crittografica.

Directory create dall'app private per default (0700) e file contenenti dati privati 0600 su Linux; non cambiare ricorsivamente permessi di directory esistenti dell'utente. Separare log tecnici redatti e report con dati privati. Rotazione iniziale proposta: massimo 5 file log da 5 MiB. Eliminare le credenziali non elimina i materiali; una futura cancellazione dei dati locali richiede selezione e conferma specifiche, fuori dalle operazioni automatiche.

Allegati/HTML decompressi contano nei limiti, non solo Content-Length compresso. Testare HTML di login o errore con status 200, MIME mancante e file HTML legittimo; estensione e header sono indizi, non prova sufficiente. Non imporre la dimensione Content-Length ai byte decompressi senza tener conto di Content-Encoding.
