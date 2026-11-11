# 22 - Check funzionale del 9 novembre 2026

Aggiornamento successivo su richiesta dell'utente:
[i link a corsi non disponibili vengono ignorati](23_IGNORA_CORSI_NON_DISPONIBILI.md),
senza i relativi avvisi. I conteggi di scansione qui riportati sono quelli precedenti
a questa nuova regola.

## Esito e ambito

Le funzioni verificate passano i controlli locali e il collaudo reale a campione.
Corretti due difetti e chiarita la causa dei precedenti 16 avvisi materiali.
Non è una garanzia su ogni piattaforma o contenuto Moodle. Nessun commit, push o
rilascio eseguito: le correzioni sono nel working tree del submodule, base a6939f4.
Credenziali, archivi e download preesistenti sono stati preservati.

## Correzioni

- **Script Linux:** il checkout Windows aveva convertito i file .sh in CRLF,
  causando errore su `set -euo pipefail`. Convertiti in LF e aggiunto il vincolo
  `*.sh text eol=lf` nel nuovo `.gitattributes` del progetto. Verificato anche lo sdist.
- **Allegato HTML reale:** il parser ora classifica il file HTML da pluginfile come
  pagina da esportare passivamente. L'exporter conserva il body completo, anche con
  classi simili a Moodle, mantenendo sanitizzazione, gestione sicura degli asset ed
  esclusione di script/frame e attributi attivi. Non salva l'originale eseguibile.
- **Corso non disponibile:** il messaggio standard nella pagina resource è ora
  classificato ACCESS_DENIED. Riconoscimento limitato al body del modulo resource
  e a un breve messaggio iniziale: non interpreta una domanda o lezione come errore.

Tre regressioni aggiunte: risposta di corso non disponibile, classificazione HTML,
body completo e sanitizzazione. Upload, consegne e nuovi tentativi restano vietati.

## Controlli locali sui sorgenti finali

| Ambiente/prova | Esito |
|---|---|
| Windows, Python 3.14.7 | 139 passati, 4 saltati |
| Linux/Xvfb, Python 3.14.4 | 143 passati, nessuno saltato |
| Wheel installata in Linux pulito | 143 passati, nessuno saltato |
| Linux, Python 3.10.22 | 143 passati, nessuno saltato |
| Linux, Python 3.12.16 | 143 passati, nessuno saltato |
| Ruff / Bandit / pip check | Superati |
| Audit online del runtime Linux fissato a versioni precise | 22 dipendenze, nessuna vulnerabilità nota segnalata |
| Build wheel e sdist | Superata |
| Pacchetti | Moduli della wheel identici ai sorgenti; esclusi dati privati; SHA256 aggiornati |

I quattro skip Windows sono tre test GUI per Tk non disponibile e un controllo
Linux no-follow. La GUI è provata su Linux con Xvfb, non su desktop Windows nativo
o desktop Linux autonomo. Gli skip non vengono conteggiati come successi.

La suite copre GUI/CLI, credenziali sintetiche, selezione, anteprima e filtri,
download/conflitti, cancellazione/limiti, backup/ripristino, sanitizzazione,
sessioni e separazione dei due utenti DB, BLOB, rollback e PDF. Lo smoke del pacchetto
installato verifica due utenti demo distinti, download, integrità, storico e PDF personali.

Benchmark con 1.000 risorse GUI e 10.000 record di manifest: caricamento manifest
76,28 ms, piano 100,96 ms, popolamento 8,96 ms, ricerca 0,32 ms, selezione 0,88 ms.
Comandi UI misurati sotto 200 ms, senza promessa su ogni condizione di carico possibile.

## FAD reale attuale

Login/logout riusciti. Nuova scansione: **32 corsi, 282 sezioni, 657 risorse**:
526 file, 48 compiti, 28 link, 28 googlemeet, 24 revisioni quiz, 3 pagine.
I conteggi del 26 ottobre sono storici e non descrivono il sito attuale.

Campione reale: file ordinario, allegato introduttivo di compito, revisione quiz già
completato e nuovo allegato HTML. Workspace e DB isolati nel progetto.

| Prova reale | Esito |
|---|---|
| Prima passata | 4 scaricati |
| Seconda passata | 2 file invariati, 2 export aggiornati |
| Verifica locale | 4 controllati, 0 problemi |
| SQLite | integrity_check=ok, 4 BLOB riletti, 0 differenze |
| PDF ReportLab | Generato e aperto con pypdf: 1 pagina |
| HTML reale | Testo visibile preservato; nessuno script/frame/oggetto attivo nell'export |

I 147 riferimenti a file censiti nel browser il **26 ottobre** sono ancora tutti
nel catalogo nuovo. È un controllo di regressione su un riferimento storico,
non un nuovo censimento visivo integrale del sito o un nuovo hash remoto di tutti i file.

## Chiarimento dei precedenti avvisi

Controllati i 17 riferimenti storici: 16 avvisi materiali e un rifiuto della policy.

- **15 riferimenti:** la FAD risponde «Questo corso al momento non è disponibile
  agli studenti». È HTML di avviso senza file nella regione principale; il limite
  riguarda la disponibilità del corso per l'account corrente. Non prova che i file
  siano stati cancellati sul server. L'app ora riporta correttamente l'accesso negato.
- **1 allegato HTML:** realmente disponibile, ora esportato correttamente nel campione.
- **1 riferimento:** redirect esterno bloccato dalla policy; destinazione non seguita.

Scansione attuale: **39 avvisi**, tutti classificati: 15 indisponibilità di corso,
23 quiz senza tentativo completato e revisionabile riconosciuto, 1 rifiuto policy.
**Zero avvisi di allegato non riconosciuto.** Nessun permesso, corso o tentativo è
stato modificato per eliminare avvisi. Gli antichi NO-GO per «16 materiali non chiariti»
sono storici: il punto è ora chiarito, ma i limiti di accesso restano e questo non
equivale a una dichiarazione di completezza universale o a un rilascio automatico.

## Evidenze e comandi

In `app/.verification-check-20261109/`, ignorata da Git: `full-windows-final.log`,
`full-linux-final.log`, `runtime-audit-live.json`, `live-check.json`,
`package-and-reference-check.json`, workspace, DB e PDF reali di prova.
Le risposte HTML diagnostiche sono private: non includerle in commit o pacchetti.
Pacchetti aggiornati e SHA256 in `.verification-artifacts/`.

Comandi principali: `check_windows.ps1`; in WSL `check_production_linux.sh --mount
edoardoquerio --compat`, con mount POSIX temporaneo nel progetto e test come utente
ordinario. I helper reali restano nell'area di verifica, separati dai test senza rete.
