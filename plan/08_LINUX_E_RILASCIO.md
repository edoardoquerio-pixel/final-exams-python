# 08 - GNU/Linux e rilascio

## Ambiente

Scegliere una versione Ubuntu supportata al momento del collaudo e registrare OS, Python, Tcl/Tk e backend keyring. Desktop reale o VM con sessione grafica e portachiavi; display virtuale per automazione GUI come verifica aggiuntiva, non sostituto.

Comandi previsti dopo aver creato il package:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m tkinter
python -m fad_downloader --help
```

L'extra dev va definito nel pyproject. Installare Tk/venv tramite package manager se necessari, verificando i nomi dei pacchetti sulla distribuzione. Per l'utente finale documentare wheel e dipendenze bloccate, senza richiedere strumenti dev.

## Checklist finale

- [ ] Installazione da checkout/wheel pulito.
- [ ] Nessun percorso Windows o dipendenza PowerShell.
- [ ] GUI con tastiera, resize e DPI.
- [ ] Keyring reale: consenso, sblocco, delete, backend assente.
- [ ] Root con spazi/Unicode, permessi negati, symlink.
- [ ] Due processi e crash: lock coerente e nessun writer fantasma.
- [ ] Rete interrotta, timeout e annullamento senza file parziali definitivi.
- [ ] Login e scan Moodle reale autorizzato.
- [ ] File, cartella, pagina e libro verificati se disponibili.
- [ ] Quiz multipli e limiti di revisione segnalati correttamente.
- [ ] Riavvio e nuove regole senza perdita mapping o rinomina implicita.
- [ ] File aggiornato e file locale cancellato gestiti.
- [ ] Report riconciliato e indice verificato nel browser.
- [ ] Nessun contenuto attivo o caricamento remoto automatico nell'export.
- [ ] Verificatore indipendente senza discrepanze.
- [ ] Segreti e audit dipendenze controllati.

## Gate rilascio

Ogni requisito ha evidenza o limitazione esplicitamente approvata. Nessun difetto critico su password, scritture fuori root, quiz, file corrotti o account. Test obbligatori non eseguiti indicati come blocchi/limitazioni. Esaminare diff, artefatti, licenze, dipendenze e assenza dati privati.

Preparare README utente, installazione, screenshot sintetici, troubleshooting, limiti e cancellazione credenziali. Pubblicazione e distribuzione esterna solo su istruzioni specifiche.

## Demo

Login → scan → nomenclatura → selezione → anteprima → pochi download → indice → nuova esecuzione → report. Errori dimostrati con fixture/server locale, senza danneggiare dati reali. Demo offline sintetica disponibile se manca la rete, chiaramente dichiarata come tale.

## Ripristino

Ultima release e backup stato/config prima delle migrazioni. Rollback non elimina materiali dell'utente. Stato incompatibile: restore o nuovo stato separato, mai azzeramento silenzioso. Conservare evidenze e problemi residui.

## Matrice di supporto da congelare in F0

Ambiente iniziale proposto: Ubuntu Desktop 24.04 LTS x86_64 con Python 3.12; confermare disponibilità, patch e dipendenze nel gate. Un ambiente isolato Linux con Python 3.10 controlla il minimo dichiarato. Altre distribuzioni, architetture, versioni e filesystem di rete non sono certificati da queste due prove. Se il minimo non è supportabile dalle dipendenze scelte, aggiornare esplicitamente requisito e proposta prima del rilascio.

Testare almeno la sessione desktop di riferimento (Wayland o X11, da registrare); non confondere esecuzione in container headless con collaudo del portachiavi desktop. Manifest/config seguono XDG e workspace scelto; package installabile senza permessi root. Lo script di sviluppo e i percorsi di installazione non devono dipendere dal repository Materie.

## Packaging e verifica finale aggiuntiva

- [ ] `pyproject.toml` definisce entrypoint, Python minimo, dipendenze runtime e extra dev.
- [ ] Lock con versioni/hash riproducibili, separando runtime e sviluppo.
- [ ] Build wheel/sdist; installazione wheel in un venv nuovo fuori dalla directory sorgente.
- [ ] GUI avviabile e CLI/help senza DISPLAY e senza import iniziale di Tk.
- [ ] Dati/config non finiscono nel package o nella directory sorgente.
- [ ] Apertura offline di raccolta, indice e report senza credenziali.
- [ ] Aggiornamento export interrotto lascia utilizzabile la generazione precedente.
- [ ] Form quiz trasformati in contenuto statico senza perdere risposte visibili.
- [ ] File locale modificato protetto, anche dopo anteprima.
- [ ] Budget e latenza annullamento misurati; eventuali limiti DNS espliciti.
- [ ] Ogni riga della matrice R01-R25 ha evidenza di accettazione.

La compatibilità minima dei test di dominio non garantisce automaticamente quella dei backend desktop: registrare separatamente i risultati. Per il confronto live annotare data e capacità effettivamente osservate: la versione Moodle della scuola non si deduce dalla documentazione pubblica.
