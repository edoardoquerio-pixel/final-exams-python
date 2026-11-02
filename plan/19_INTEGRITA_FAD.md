# 19 - Confronto diretto con la FAD, 26 ottobre 2026

**Verifica successiva:** [20_CONFRONTO_SITO_GUI.md](20_CONFRONTO_SITO_GUI.md).
Il confronto dal sito ha individuato ulteriori omissioni nel catalogo: l'integrità
dei file già scaricati documentata qui non certifica la completezza della raccolta.

## Esito

**438 file originali su 438 coincidono con la FAD per dimensione e SHA256.**
Una delle due pagine HTML locali è invece meno aggiornata della versione attualmente
servita dalla FAD: contiene 100 caratteri di testo in meno. Non è una corruzione locale:
entrambe le copie precedenti coincidono con i rispettivi manifest.
Restano aperte le 16 attività senza materiale riconosciuto. Il gate rimane **NO-GO**
per la completezza della raccolta, come nel registro 18.

## Ambito e metodo

Prova Linux/WSL, account e tutti i corsi accessibili già autorizzati dall'utente.
Riferimento locale: ultimo collaudo in `app/.verification-live/`, con il workspace
principale e il workspace separato del ritest delle due pagine. Non è una verifica
di eventuali installazioni o archivi esterni a questi workspace.

- Nuova scansione autenticata: 32 corsi, 564 risorse, nessun ID aggiunto o rimosso.
  Le 463 risorse supportate hanno tutte una copia locale nei workspace considerati.
- GET incondizionati: nessun If-None-Match/If-Modified-Since, Cache-Control no-cache,
  solo risposte 200. Hash calcolati direttamente sui blocchi di risposta con hashlib,
  senza il downloader, il suo controllo 304 o la sua funzione di verifica locale.
- Rilettura dei byte locali e controllo separato dei manifest, senza sovrascriverli.
- 3.282.121.861 byte nuovamente trasferiti per il confronto dei file e dell'asset.
  Questo totale non comprende i documenti HTML usati per scansione ed export.
- Le pagine e le revisioni quiz sono trasformate dall'app: l'HTML grezzo Moodle non
  deve essere identico all'export. Confrontati gli export rigenerati e, separatamente,
  frammenti di testo delle domande/feedback, testo delle pagine e marcatori di selezione.
  La rigenerazione riusa l'exporter dell'app; non è una validazione indipendente di
  ogni scelta del sanitizer, della resa visiva o di tutte le tipologie di risposta.

## Risultati misurati

| Controllo | Risultato |
|---|---|
| Originali file | 438 identici, 0 diversi o non confrontati |
| Asset incorporato | 1 identico alla FAD |
| Manifest delle risorse | 463 corrispondenti ai byte locali |
| Revisioni quiz completati | 23 export identici alla nuova rigenerazione |
| Selezioni quiz | 750 selezionate e 2.337 non selezionate: conteggi corrispondenti in tutti i 23 export |
| Pagine | 1 export identico, 1 differente |
| Testi di quiz e pagine | 2.101 frammenti controllati; 2 assenti dalla copia locale della pagina differente |
| SQLite | 2 DB integri; 458 oggetti BLOB riletti, 3.268.754.423 byte; nessun hash/dimensione o ordine dei blocchi errato |
| Collegamento DB/FAD | Tutti gli 876 riferimenti primari ai file, nelle due passate storiche, coincidono con dimensioni/hash FAD appena misurati |
| Sessioni remote | Logout riuscito dopo entrambe le prove |

### Pagina meno aggiornata

Differenza confermata dalla prova completa e da un secondo controllo degli export.
Titolo invariato; entrambe le copie precedenti hanno 4.419 byte, il nuovo export
4.523 byte. Il confronto del testo normalizzato rileva una singola aggiunta di 100
caratteri, non una differenza di soli spazi o di normalizzazione Unicode.
I 2 frammenti mancanti appartengono a questa pagina, non ai quiz.
Non è stato stabilito quando sia stato aggiornato il contenuto remoto.
La copia locale è stata conservata: nessun aggiornamento dei download o del DB
di collaudo è stato eseguito per nascondere la differenza. Andrà riscaricata per
allinearla al contenuto attuale.

## Limiti sulla completezza

La nuova scansione conserva 37 avvisi: 16 materiali non riconosciuti, 20 quiz senza
tentativo completato/revisionabile riconosciuto, 1 collegamento rifiutato dalla policy.
Le 101 attività diverse dalle risorse supportate restano 28 link, 28 googlemeet,
45 consegne; upload escluso dal requisito corrente.

`core_course_get_contents` non ha fornito un inventario utilizzabile per nessuno
dei 32 corsi. Il conteggio zero dei file di riferimento API **non significa assenza
di allegati**. La scansione HTML è quella dell'app stessa: conferma la stabilità
del catalogo, ma non dimostra da sola che non esistano materiali sfuggiti al parser.
Le diagnosi dei 16 materiali nel registro 18 restano valide e non sono state risolte
da questo confronto. Nessun nuovo tentativo quiz, consegna o accesso a host esterni.

## Ripetibilità ed evidenze

`app/verify_fad_integrity.py` ripete il confronto sul precedente collaudo locale.
`--exports-only` usa il catalogo salvato e ricontrolla soltanto gli export HTML.
Il programma legge internamente `.env`, richiede un account coerente con i manifest,
mantiene i limiti di trasferimento e non stampa credenziali, titoli o contenuti privati.
Richiede l'autorizzazione alla prova reale; non fa parte dei test automatici.

Due sottocartelle `integrity-*` nell'ultimo collaudo contengono summary/details,
la nuova copia privata della pagina differente e la classificazione del confronto.
Nella prima sono presenti anche `sqlite-integrity.json` e
`sqlite-fad-comparison.json`. Sono ignorate da Git. Un riepilogo senza dati personali
è in `.verification-artifacts/integrity-readiness.json`.

Otto test sintetici del nuovo verificatore passati su Windows e Linux: nuovi byte,
assenza di richieste condizionali, rifiuto 304, risposta troncata, limite di byte,
modifica locale/percorso esterno, perdita di testo e conteggio selezioni con deduplica.
Ruff e Bandit sul nuovo strumento senza segnalazioni. Nessuna modifica al runtime
dell'app né rebuild del pacchetto richiesto da questa verifica.
