# 03 - Fasi di implementazione

| Fase | Lavoro | Gate di uscita |
|---|---|---|
| F0 | Inventario, requisiti, ambiente Linux | Workspace delimitato e avvio riproducibile |
| F0A | Prove di fattibilità sui punti incerti | Login/scansione, quiz, Tk/keyring e cancellazione verificati con scope limitato |
| F1 | Package, modelli, errori, config e log | Import senza rete; schemi validati |
| F2 | URL, percorsi, template, lock, atomicità | Test negativi e nessuna scrittura esterna |
| F3 | HTTP, login, keyring, logout | TLS, backend approvato, account isolati |
| F4 | Scansione e mapping | Paginazione, fallback, risultati parziali |
| F5 | Selezione e piano | Anteprima stabile; simulazione senza materiali |
| F6 | File/cartelle e stato | Integrità, crash, collisioni, aggiornamenti |
| F7 | Pagine/libri e asset | Completezza e sanitizzazione verificati |
| F8 | Quiz completati | Sola lettura, review multipagina, permessi |
| F9 | GUI e annullamento | UI reattiva, sessione scaduta e cleanup |
| F10 | Report, indice, retry, CLI | Conteggi e parità GUI/CLI |
| F11 | Ubuntu, hardening, documentazione | Gate rilascio ed evidenze reali |

## Procedura per fase

1. Definire contratto ed esempi prima del codice.
2. Scrivere test ordinari e avversi su risultati attesi indipendenti dall'algoritmo.
3. Implementare modifiche contenute.
4. Eseguire test della fase e regressioni dei confini toccati.
5. Passata di review distinta; correggere e ripetere verifiche coinvolte.
6. Registrare comandi, risultati e limiti nel registro.

Non passare con difetti di credenziali, integrità o permessi aperti. Non indebolire un test per ottenere verde.

## Prova reale

Credenziali inserite dall'utente localmente. Prima simulazione su un corso, poi pochi file in output isolato. Confronto manuale con contenuti visibili nel browser. API non disponibile attiva fallback documentato, senza modificare permessi Moodle.

## Tempistica

Termine indicativo fine novembre 2026. Nessuna stima delle ore. Prima completare i requisiti concordati; nuove funzionalità e riduzioni di ambito richiedono una decisione registrata.

## F0A: anticipare i rischi prima dello sviluppo completo

La sequenza è F0 → F0A → F1-F11. F0A usa un piccolo esperimento isolato: non richiede la GUI definitiva né tutti gli adapter. L'utente inserisce le credenziali; l'AI riceve soltanto risultati redatti.

- Confermare quale flusso login è disponibile e se l'account reale può essere identificato.
- Verificare un corso: paginazione, sezioni non immediatamente visibili e risorse. Annotare versione/tema solo se rilevabili, non inventarli.
- Verificare una revisione quiz completata, la paginazione e la rappresentazione delle risposte nei controlli HTML; un caso con feedback limitato.
- Provare Tkinter e backend keyring su desktop Ubuntu; fissare la matrice Python/Tk.
- Misurare annullamento con rete lenta, DNS bloccato e attesa socket; decidere se il worker thread è sufficiente o serve isolamento in processo.

Se un contenuto non è disponibile nell'account, usare fixture sintetica per sviluppo e lasciare la verifica live aperta. Un fallimento strutturale di login o quiz deve portare a una decisione prima di investire nelle schermate complete; non certificare la funzionalità con soli mock.

## Evidenza richiesta a ogni gate

Usare [la matrice](10_TRACCIABILITA.md) per collegare fase, requisito e test. F7/F8 devono testare l'intera esportazione, compresi gli asset; F9 deve usare errori reali simulati dei servizi, non soltanto una demo grafica. F11 esegue installazione da wheel e verifica offline. Preferire unità di lavoro piccole; nessuna proliferazione di framework o servizi oltre il progetto desktop.
