# Configurazione e collaudo — 26 ottobre 2026

## Ambiente predisposto

Creato `app/.venv-verifica/`, Python 3.14.7, con strumenti dev e build.
Il virtualenv usa system-site-packages: è dedicato al progetto ma non totalmente
isolato dalle dipendenze di base. Nessun pacchetto è stato aggiornato nell'ambiente condiviso.
Installati localmente setuptools/wheel e le dipendenze dichiarate; ReportLab 5.1.0.
Versioni locali salvate in `.verification-artifacts/windows-verification-packages.txt`:
non è un lock completo con hash né include tutti i pacchetti ereditati.
Virtualenv e directory di verifica esclusi da Git.

`check_windows.ps1` rende ripetibili i controlli e si ferma a un codice di uscita non zero.
Eseguito anche integralmente con uscita 0; log locale in
`.verification-artifacts/check-windows.log` (test saltati restano esplicitati nel log).
`smoke_release.py` conserva configurazioni e dati sintetici sotto il progetto e li rimuove
alla fine. Non usa il `.env` reale. Gli script Linux precedenti usano ancora HOME:
non sono stati eseguiti; i test Linux sono stati invocati direttamente nel progetto.

## Esiti effettivi

- Suite Windows con nuovo ambiente: **121 passati, 4 saltati**, 11,57 s.
- Suite Ubuntu WSL con Xvfb: **124 passati, 1 fallito**, 39,23 s.
  I tre test GUI e il test no-follow sono passati.
- Fallimento Linux: `test_rotation_and_private_permissions`, atteso 0600,
  osservato 0777 sul volume Windows montato in `/mnt/c`. Il filesystem non
  applica la semantica chmod richiesta. Non è stato aggirato o marcato come passato.
- Build senza isolamento riuscita: sdist e wheel correnti in `.verification-artifacts/`.
- Wheel installata senza rete in `.verification-installed/`; import verificato da questa
  directory, non da `src/`. Prova completata con due utenti ordinari, download demo,
  integrità, storico e PDF personali.
- Ruff (incluso lo script smoke), Bandit e pip check superati.
- Il primo tentativo smoke interpretava erroneamente l'output testuale report-pdf come JSON:
  corretto lo script di prova e ripetuto con successo; nessun difetto applicativo correlato.

La GUI Windows non trova `init.tcl`: il messaggio precedente «display non disponibile»
nei test era generico. La GUI è stata invece esercitata con successo su Ubuntu/Xvfb.
Non modificata l'installazione Python globale di Windows.

## Limiti ancora aperti

Per verificare permessi 0600 occorre una copia di progetto su filesystem Linux con
semantica POSIX, oppure un mount configurato per conservarli. Non è stata modificata
la configurazione globale di WSL e non sono stati creati workspace esterni al progetto.
I log sul mount attuale non hanno la garanzia 0600: non usarlo come prova di protezione POSIX.

Restano da collaudare desktop Linux autonomo, Python 3.10/3.12, confronto FAD reale,
latenza/annullamento sotto carico e crash estesi. Nessun nuovo audit online vulnerabilità
né prova FAD live; nessun dato reale o upload usato. Il disallineamento keyring/.env
resta documentato nell'audit requisiti. Nessuna nuova release pubblicata.

Questo registro aggiorna i punti build/GUI del registro 15 e dell'audit 16:
la build corrente non è più bloccata da setuptools; GUI Linux verificata con Xvfb,
prova permessi POSIX fallita sul mount Windows.
