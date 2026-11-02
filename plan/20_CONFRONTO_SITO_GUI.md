# 20 - Materiali sul sito FAD rispetto al catalogo della GUI

**Correzione successiva:** [21_CORREZIONE_COMPLETEZZA.md](21_CORREZIONE_COMPLETEZZA.md).
I 76 riferimenti mancanti individuati qui sono ora presenti e sono stati scaricati.
Questo documento conserva l'evidenza del difetto precedente.

Data: 26 ottobre 2026. **Esito negativo: l'app non elenca tutti i riferimenti a file
visibili sul sito.** Questo controllo risponde alla richiesta sito → app e non va
confuso con il precedente confronto degli hash dei soli file già individuati.

## Come è stata eseguita la verifica

L'utente ha effettuato l'accesso alla FAD nel browser integrato. Da quella sessione
sono stati aperti i 32 corsi e tutte le 279 sezioni attraverso i collegamenti del
tema Snap, attendendo il caricamento dei rispettivi elementi DOM. Due sezioni iniziali
non aperte automaticamente sono state recuperate esplicitamente prima di chiudere
il censimento. Non è stato usato il parser Moodle dell'app per costruire questo elenco.

Osservati 632 moduli: 368 resource, 11 folder, 44 assign, 43 quiz, 27 url,
28 googlemeet, 1 page e 110 label. I conteggi dei moduli non sono conteggi dei file:
le cartelle contengono più allegati e i testi possono richiamare altre attività.

Sono state aperte le 10 cartelle con collegamento accessibile, censendo 44 file;
la cartella restante non esponeva un collegamento di apertura. Sono state aperte
anche le 44 pagine di compito nei moduli e un ulteriore compito richiamato nel testo,
per un totale di 45 pagine. Solo lettura: nessuna consegna, nuovo tentativo o upload.

La finestra dell'app è stata letta tramite screenshot: scansione conclusa, filtro
«Tutti», ricerca vuota, 32 corsi / 279 sezioni / 564 risorse. Il workspace corrente
è stato identificato nel pannello «Cartelle e nomenclatura». Il catalogo di quella
scansione è stato riletto in sola lettura e copiato nell'area privata del progetto:
non è il DB di collaudo e non è soltanto il precedente catalogo storico.

I collegamenti osservati sul sito sono stati confrontati con gli URL dei record
di tipo file di questo catalogo. Per non riportare nomi o URL privati nei documenti
si sono trasferite impronte SHA256 degli URL canonici, abbreviate a 16 cifre hex;
non sono hash del contenuto del file. Rimosse credenziali/query di sessione,
normalizzato il percorso percent-encoded e ignorato forcedownload. Per i 23 link
con time è stato ripetuto anche il confronto ignorando time: nessuno era già
presente sotto l'URL senza quel parametro.

La GUI crea le righe delle risorse esclusivamente da `self.catalog.resources`
in `gui.py::populate`: un allegato assente da questo catalogo non può comparire
come file nella raccolta. Non è stata eseguita una ricerca manuale di ogni singola
riga della GUI: il controllo dei record usa il catalogo effettivamente mostrato.
Gli ulteriori tentativi di digitazione nella finestra WSLg sono falliti con errori
di riconoscimento del processo in primo piano; non vengono dichiarati riusciti.

## Risultati del confronto di 147 riferimenti distinti a file

| Categoria sul sito | Presenti nel catalogo GUI | Assenti |
|---|---:|---:|
| File di cartelle, compresi 2 richiamati nel corso | 46 | 0 |
| Allegati nei testi label | 20 | 22 |
| Allegati introduttivi dei compiti | 4 | 11 |
| Collegamento diretto mod_resource nel testo | 1 | 0 |
| File delle consegne già effettuate | 0 | 40 |
| PDF di feedback/correzione | 0 | 3 |
| Totale | 71 | 76 |

**33 riferimenti a materiali didattici omessi**: 23 nel corso C# e 10 nel corso
Python. Separatamente, mancano 40 riferimenti a file consegnati e 3 a feedback.
Le consegne/feedback sono letture di contenuti già presenti: non sono l'upload
rimandato dall'utente. Non è stato implementato o attivato un uploader.

I 147 riferimenti non sono l'intero patrimonio della FAD: comprendono allegati
nei testi, nelle cartelle e nei compiti, non l'apertura individuale di tutti i 368
moduli resource o di ogni revisione quiz. I 33 casi didattici bastano comunque
a confutare la completezza dell'elenco dell'app.

## Cause individuate

1. **Parametro time nei link pluginfile.** Tutti i 23 collegamenti temporizzati
   osservati nel corso C# sono assenti anche cercando l'URL senza time. Sono
   22 link mod_label/intro e 1 mod_assign/intro. `network.py::validate_url` ammette
   soltanto forcedownload/token su pluginfile; `moodle.py::file_links` intercetta
   il rifiuto e scarta il link senza un avviso specifico. Queste omissioni non
   erano quindi comprese nei precedenti 16 avvisi materiali.
2. **Allegati dentro i compiti.** `Moodle.expand` apre resource/folder e quiz,
   ma per assign restituisce il solo collegamento all'attività. I 10 allegati
   introduttivi Python, visibili aprendo le pagine dei compiti, non sono acquisiti.
   Lo stesso limite riguarda i 40 file di consegna e i 3 feedback rilevati.

Per un collegamento con time il download dal browser è effettivamente riuscito:
non è soltanto un collegamento ipotizzato dal codice. Questa è una prova campione,
non un download integrale di tutti i 33 riferimenti omessi; non si certifica qui
la disponibilità dei byte di ciascuno degli altri collegamenti.

## Evidenze e stato

In `app/.verification-site/`, ignorata da Git: copia privata del catalogo della
GUI, `browser-files.json`, confronto dei file, elenco delle impronte assenti e
`time-parameter-check.json`. I file temporanei del download browser non sono stati
incorporati nei pacchetti. Riepilogo senza contenuti privati in
`.verification-artifacts/site-visibility-readiness.json`.

Nessuna modifica al runtime dell'app effettuata in questa verifica. Il gate rimane
**NO-GO**: alla diagnosi precedente si aggiungono omissioni reali nell'individuazione
dei materiali. I 438 hash corretti del registro 19 provano l'integrità di ciò che
era stato individuato, non la completezza rispetto al sito.

La correzione dovrà gestire in modo circoscritto il parametro temporale dei file
e l'estrazione in sola lettura degli allegati dei compiti, mantenendo la policy di
origine e il divieto di consegne/nuovi tentativi. Serviranno test di regressione e
un nuovo confronto contro queste evidenze prima di dichiarare chiusi i difetti.
