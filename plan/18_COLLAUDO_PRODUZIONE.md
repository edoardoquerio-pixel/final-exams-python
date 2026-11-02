# Collaudo per produzione Linux — 26 ottobre 2026

**Esito: NO-GO per la raccolta completa richiesta.** I controlli automatici passano,
ma restano 16 attività/materiali senza file riconosciuto. Una pagina difettosa è stata
corretta e verificata dal vivo. Un collegamento verso un altro host resta escluso
dalla policy: non è stato aggirato. Nessuna pubblicazione o messa in esercizio effettuata.

## Perimetro e autorizzazione

L'utente ha indicato Linux come destinazione e autorizzato il collaudo in sola lettura
su tutti i corsi FAD accessibili. Non sono autorizzati upload, consegne o nuovi tentativi.
Le credenziali sono lette internamente dall'applicazione, senza visualizzarle o copiarle
nei report. Il collaudo reale usa un workspace e DB separati in `app/.verification-live/`.
I contenuti di questa directory sono privati e ignorati da Git.

## Verifiche automatiche concluse

| Ambiente/prova | Esito |
|---|---|
| Linux Python 3.14.4, sorgenti, Xvfb e filesystem POSIX temporaneo | 129 passati, nessuno saltato |
| Linux Python 3.14.4, wheel installata in venv pulito | 129 passati, nessuno saltato |
| Installazione Linux offline, lock e hash richiesti | Riuscita; suite wheel 129 passati |
| Linux Python 3.10.22, wheel in ambiente dedicato | 129 passati, nessuno saltato |
| Linux Python 3.12.15, wheel in ambiente dedicato | 129 passati, nessuno saltato |
| Windows Python 3.14.7, comando completo finale | 125 passati, 4 saltati per Tk/POSIX |
| Ruff e Bandit | Nessuna segnalazione |
| Coerenza dipendenze con pip check | Superata nei diversi ambienti |
| Audit online dipendenze runtime Linux 3.14 effettivamente installate | Nessuna vulnerabilità nota rilevata alla data della prova |
| Pacchetto: controllo nomi file inclusi | Nessun `.env`, DB o directory temporanea rilevato |
| Due utenti, download, integrità, storico e PDF sulla wheel installata | Superato |

I due test nuovi verificano che l'annullamento interrompa un Retry-After di 30 secondi
senza inviare un'altra richiesta, e che uno stream oltre il budget non pubblichi altri chunk.
Non simulano un resolver DNS bloccato né sostituiscono una misura generale di cancellazione.
Altri due test verificano il fallback per le pagine senza `.no-overflow`: contenuto
preservato, script/navigazione esclusi e nessun fallback su una pagina di corso generica.

Benchmark sintetico: 1.000 risorse GUI e manifest con 10.000 record. Prima misura:
caricamento manifest 75,86 ms, piano 99,03 ms, popolamento 8,70 ms, ricerca 0,41 ms,
selezione 0,93 ms. I comandi UI misurati rientrano nell'obiettivo di 200 ms.
Le misure successive sono nel JSON locale `production-stress.json`; non costituiscono
una garanzia di prestazioni su ogni sistema.

Il precedente fallimento 0600 sul mount Windows è stato distinto dal comportamento
POSIX: la suite su tmpfs POSIX passa senza saltare il controllo dei permessi.
Il mount è creato solo sotto il progetto e smontato da una trap a fine comando.
Non sono state modificate configurazioni globali WSL o installazioni Python di sistema.

Interpreti 3.10/3.12 e ambienti di prova erano nell'area temporanea e sono stati rimossi
con lo smontaggio; le versioni dei pacchetti restano nei registri locali generati.

## Artefatti locali

In `app/.verification-artifacts/`:

- wheel e sdist 0.2.0 correnti, senza pubblicazione;
- `requirements-production-linux.lock`: 22 dipendenze runtime con SHA256;
- `wheelhouse-linux/`: wheel per Linux x86_64 / CPython 3.14 provate offline;
- `SHA256SUMS` e `SHA256.json`: integrità dei pacchetti e del lock;
- log `production-linux*.log`, `production-compatibility.log`, `production-windows-final.log`;
- freeze delle dipendenze e risultati JSON dell'audit.
- `release-readiness.json`: verdetto NO_GO e riepilogo verificabile dei controlli.

Ultimo controllo concluso con successo: console entrypoint, installazione offline,
suite della wheel 129 passati e benchmark. SHA256SUMS/JSON riletti e verificati;
tutti i moduli Python della wheel coincidono byte per byte con i sorgenti correnti.
Il controllo nomi file inclusi è stato ripetuto anche sull'ultima build.

Il lock binario 3.14 non è un lock universale per 3.10/3.12 o altre architetture.
Queste versioni hanno risolto e provato separatamente le dipendenze, documentate nei freeze.

`check_production_linux.sh --mount UTENTE --compat`, eseguito come root in WSL,
predispone solo il mount temporaneo; i test sono eseguiti come utente ordinario.
`prepare_linux_lock.py` prepara wheelhouse, lock e manifest; `live_acceptance.py`
è un comando esplicito di test reale, da non aggiungere alla suite automatica o eseguire senza autorizzazione.

## Collaudo reale completato

Login riuscito. Scansione: 32 corsi, 279 sezioni, 564 risorse;
463 risorse supportate (438 file, 23 review quiz, 2 pagine).
Le 101 altre attività sono 28 link, 28 googlemeet e 45 consegne: nessun invio effettuato.

Avvisi: 20 quiz senza tentativi completati/revisionabili riconosciuti,
16 attività senza allegati riconosciuti e 1 URL/azione rifiutata dalla policy.
La scansione non va dichiarata completa senza chiarire questi casi.

Prima passata: 462 risorse scaricate/archiviate e 1 pagina non riconosciuta.
Seconda passata: 438 file invariati, 24 export HTML aggiornati, stessa pagina esclusa.
Verificatore: 463 file controllati, 0 problemi. SQLite: `integrity_check=ok`;
926 righe di storico. PDF reale generato e aperto con pypdf: 50 pagine.
Contenuto di un BLOB campione da 1.050.655 byte riletto da SQLite e hash SHA256 verificato.
Non è una rilettura integrale di tutti i BLOB dopo il commit.

La pagina esclusa aveva contenuto sotto `.generalbox` senza il wrapper `.no-overflow`.
Corretto solo il fallback `#page-mod-page-view #region-main .generalbox`, mantenendo
la sanitizzazione e senza ampliare endpoint o selezionare l'intera regione principale.
Ritest reale su entrambe le pagine: 2 scaricate, 2 file verificati, 0 problemi,
testo visibile preservato (confrontato in memoria senza riportarlo nei prompt).
Sono quindi verificate 438 risorse file, 23 review quiz e 2 pagine attraverso la prima
prova e il ritest mirato. Il report del primo workspace conserva l'esito precedente,
senza falsificarlo retroattivamente; la correzione ha un workspace/DB di prova separati.

Approfondimento dei 16 avvisi materiali: 15 risposte HTML del modulo resource con
notifica e senza link file riconosciuto; 1 risposta HTML diretta da `pluginfile`
(estensione `.html`, 34.372 byte). Non erano video/audio nascosti nei selettori provati.
Non è stata provata l'assenza del contenuto sul server e non si dichiarano vuote queste attività.
Serve chiarire disponibilità/rendering delle prime e il trattamento sicuro del file HTML.
Il controllo supplementare ha inoltre confermato un redirect verso un host diverso,
rifiutato prima di seguirlo. Nessuna credenziale è stata inviata a quell'host.

La diagnosi ha consultato i sorgenti pubblici ufficiali Moodle
[view.php](https://raw.githubusercontent.com/moodle/moodle/MOODLE_311_STABLE/mod/resource/view.php)
e [locallib.php](https://raw.githubusercontent.com/moodle/moodle/MOODLE_311_STABLE/mod/resource/locallib.php).
Questo riferimento non identifica con certezza la versione installata sulla FAD.

I DB reali di collaudo usano utenti locali temporanei con password casuali non conservate;
non sono configurazioni di account da adottare in produzione. I file scaricati e i PDF
restano locali nella cartella ignorata da Git; non sono incorporati nei pacchetti.

## Gate di rilascio

Verifica successiva: [19_INTEGRITA_FAD.md](19_INTEGRITA_FAD.md). I 438 file coincidono
con nuovi download FAD, senza cache; tutti i BLOB sono stati riletti. Una pagina locale
risulta meno aggiornata della versione remota (100 caratteri aggiuntivi). I risultati
di prima/seconda passata sopra restano lo storico del collaudo precedente.

Gli esiti automatici sono positivi, ma non si dichiara chiusa la completezza R04/R09
finché le 16 attività non sono risolte o classificate con evidenza. La correzione pagine
R10 è verificata; nessun libro era disponibile nel catalogo reale di questa prova.
Restano non esaustive le prove su DNS bloccante e crash; il benchmark copre solo le
operazioni sintetiche dichiarate. Non è stato verificato un desktop Linux autonomo.
R03 è stato riallineato alla scelta `.env` già registrata nel documento 13:
nessun cambio silenzioso al login, nessuna promessa di cifratura tramite keyring.
