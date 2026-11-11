# 09 - Registri operativi

## Controllo dei 23 quiz, 9 novembre 2026

[Esito attuale](24_CONTROLLO_QUIZ_2026_11_09.md): 47 pagine lette, 25 con revisione,
22 senza (6 completati con revisione non permessa, 6 vincolati al profilo, 10 senza
cronologia visibile). Una delle precedenti 23 revisioni è ora disponibile: esportata,
HTML e 4 allegati verificati senza problemi. Nessun tentativo avviato o inviato;
nessuna modifica al runtime richiesta dai risultati di questo controllo.

## Esclusione richiesta dall'utente, 9 novembre 2026

[Regola corrente](23_IGNORA_CORSI_NON_DISPONIBILI.md): ignorare senza avvisi i link
che restituiscono il messaggio di corso non disponibile agli studenti. Codice distinto
COURSE_UNAVAILABLE e gestione mirata nel ciclo di scansione; nessuna esclusione permanente.
Ritest di 17 riferimenti reali: 15 ignorati, 1 HTML conservato, 1 avviso policy mantenuto.
Windows 141 passati + 4 skip; nuove regressioni su altri errori e nuove scansioni.

## Check completo del 9 novembre 2026

[Registro attuale](22_CHECK_COMPLETO_2026_11_09.md): submodule recuperato, 143 test
su Linux 3.10/3.12/3.14 e wheel pulita; Windows 139 + 4 skip. Corretti CRLF degli
script Linux e gestione passiva degli HTML allegati. Chiariti i precedenti avvisi:
15 riferimenti a corsi non disponibili agli studenti, 1 HTML ora esportato correttamente.
Scansione reale: 32 corsi, 282 sezioni, 657 risorse; quattro campioni scaricati,
incrementale, BLOB e PDF verificati. Zero allegati non riconosciuti; 39 avvisi
classificati (15 indisponibilità, 23 quiz senza review riconosciuta, 1 redirect esterno).
Audit delle 22 dipendenze runtime senza vulnerabilità note. Nessun push o rilascio.

## Correzione del confronto sito → app, 26 ottobre 2026

[Esito della correzione](21_CORREZIONE_COMPLETEZZA.md): gestiti time numerico e
lettura allegati dei compiti. Tutti i 147 riferimenti browser presenti; 76 file
prima assenti e 2 pagine scaricati, seconda passata corretta, 78 BLOB senza problemi,
PDF di 9 pagine. GUI aggiornata con due casi reali verificati visivamente.
Linux 140 test passati su ciascuna versione 3.10/3.12/3.14 e sulla wheel installata;
Windows 136 + 4 skip. Rimangono i precedenti avvisi, senza ampliamento degli host.

## Confronto sito → GUI del 26 ottobre 2026

[Verifica dal browser](20_CONFRONTO_SITO_GUI.md): 32 corsi e 279 sezioni aperti,
10 cartelle accessibili e 45 pagine di compito controllate. Confrontato il catalogo
della scansione corrente nella GUI, non il DB storico. Fra 147 riferimenti a file,
33 materiali didattici, 40 consegne e 3 feedback non sono elencati. Individuati il
rifiuto silenzioso del parametro time e la mancata espansione dei compiti. Runtime
non modificato; completezza non raggiunta. Download campione di un file omesso riuscito.

## Integrità rispetto alla FAD del 26 ottobre 2026

[Confronto diretto](19_INTEGRITA_FAD.md): 438 file e 1 asset identici alla FAD,
23 quiz identici, 1 pagina identica e 1 meno aggiornata (100 caratteri aggiuntivi remoti).
458 BLOB riletti senza errori; 876 riferimenti file DB confrontati con la FAD.
Nuovo verificatore e 8 test sintetici passati su Windows/Linux; Ruff/Bandit puliti.
Nessun download precedente sovrascritto. Restano i 16 materiali non riconosciuti:
nessuna dichiarazione di completezza o via libera alla produzione.

## Gate produzione del 26 ottobre 2026

Esito corrente: [18_COLLAUDO_PRODUZIONE.md](18_COLLAUDO_PRODUZIONE.md).
129 test superati su Linux 3.10/3.12/3.14; collaudo reale e ritest pagine conclusi.
Nessun via libera alla raccolta completa: restano 16 materiali non riconosciuti.
R03 riallineato alla scelta .env già vigente. Nessuna pubblicazione o upload.

## Ripresa del 26 ottobre 2026

Aggiornamento successivo: [verifiche eseguite](15_VERIFICHE_2026_10_26.md).
121 test passati, 4 saltati; ulteriori casi CLI superati. Ruff/Bandit/pip check superati.
Build non completata per setuptools assente. La nota seguente sul selettore non verificato
è conservata come stato precedente alla prova.

Contesto consolidato in [00_CONTESTO_ATTUALE.md](00_CONTESTO_ATTUALE.md): requisiti
dell'utente, mappa del codice, prove storiche, limiti e prossimo passo. Upload rimandato
per istruzione dell'utente. Il selettore CLI `--resource-id` e il relativo test sono
modifiche in corso senza esito di test confermato; questa riorganizzazione documentale
non ne certifica il funzionamento.

## Stato iniziale

| Fase | Stato | Evidenza | Problemi |
|---|---|---|---|
| F0, F0A, F1-F11 | In corso, con ambito sperimentale 0.0.1 | [Registro versione](12_VERSIONE_0_0_1.md): test offline e Linux | Gate finali e prove Moodle reali ancora aperti |
| Revisione documentale 1.1 | Verificata | [Esito](11_REVISIONE.md) e [matrice](10_TRACCIABILITA.md) | Prove Linux/Moodle ancora da eseguire |

Espandere una riga per fase all'avvio. Stati: da eseguire, in corso, verificata, bloccata. «Verificata» richiede evidenza, non soltanto codice generato.

## Scheda task

Versione 0.2.0 del 15 ottobre: [SQLite, utenti DB e PDF](14_DATABASE_UTENTI_PDF.md).
R26-R28 implementati e provati su dati sintetici; i gate di compatibilità Moodle già aperti
restano invariati. Due utenti DB ordinari, contenuti BLOB, report per proprietario e importazione locale.

Aggiornamento 0.1.0: [copertura dei requisiti e prove effettuate](13_VERSIONE_0_1_0.md).
Implementazione del flusso completo, test offline e Ubuntu verificati; login reale rifiutato,
gate F0A e validazione finale ancora aperti.

```text
ID / fase / requisiti:
Data / versione / commit:
File previsti e modificati:
Contratto / motivazione:
Comandi / esiti:
Prove indipendenti:
Verifiche sicurezza:
Non eseguito / motivo:
Difetti aperti:
Decisione / prossima azione:
```

## Rischi

| ID | Rischio | Azione | Stato |
|---|---|---|---|
| K01 | API/tema Moodle differenti | Adapter, fallback e confronto live | Aperto |
| K02 | Quiz non accessibile/incompleto | Limiti espliciti e confronto browser | Aperto |
| K03 | Keyring assente/bloccato | Login senza memoria e backend approvati | Aperto |
| K04 | GUI bloccata/eventi tardivi | Worker, coda, run/account ID | Aperto |
| K05 | Termine non rispettato | Gate e controllo ambito | Aperto |
| K06 | Dati privati in log/fixture | Anonimizzazione e sentinelle | Aperto |
| K07 | Collisioni e race | Aperture sicure, lock, prove subprocess | Aperto |
| K08 | Sanitizzazione elimina risposte quiz | Estrazione statica prima del filtraggio, T07 | Aperto |
| K09 | Export HTML/asset aggiornato a metà | Generazioni e pubblicazione atomica, T06 | Aperto |
| K10 | Timeout non limita annullamento totale | Esperimento F0A e T08/T12 | Aperto |
| K11 | File locale modificato sovrascritto | Conflitto e verifica al commit, T05 | Aperto |
| K12 | Requisiti supportati solo sulla carta | Matrice e prove live anticipate | Aperto |

## Decisioni iniziali

| ID | Decisione | Motivo | Riesame |
|---|---|---|---|
| D01 | GUI/CLI condividono servizi | Coerenza | F9/F10 |
| D02 | Worker rete seriale iniziale | Ridurre race e carico server | Solo su bisogno misurato |
| D03 | Keyring approvato, niente fallback plaintext | Proteggere password | F3/Ubuntu |
| D04 | JSON versionati | Leggibilità e migrazioni | F6 |
| D05 | Quiz completati e sola lettura | Ambito concordato | F8 |
| D06 | Nessuna rinomina implicita | Protezione dati esistenti | F5 |
| D07 | Ripresa per file completati, niente HTTP Range iniziale | Ridurre stato e casi di corruzione | F6 |
| D08 | Export composto in generazioni | Vecchia copia navigabile durante update/crash | F7/F8 |
| D09 | Workspace legato a origine/account | Impedire adozione incrociata dei materiali | F3/F6 |
| D10 | Estrarre risposte prima di sanitizzare HTML | Conservare i dati visibili senza form attivi | F8 |
| D11 | Probe di fattibilità F0A prima del prodotto completo | Scoprire incompatibilità senza ritardo | F0A |

## Decisioni tecniche ancora aperte

| ID | Decisione | Scadenza | Evidenza necessaria |
|---|---|---|---|
| O01 | Versioni Ubuntu/Python/Tk/keyring effettive | F0/F0A | Ambiente riproducibile e prova desktop |
| O02 | Endpoint e flusso login supportati dalla FAD | F0A | Prova autorizzata, solo metadati redatti |
| O03 | Libreria e configurazione sanitizzazione | F1 | Compatibilità/licenza e corpus avverso |
| O04 | Thread o processo per worker e garanzia cancellazione | F0A | DNS/socket lenti, limite misurato |
| O05 | Parser quiz e tipi di domanda effettivi | F0A/F8 | Review visibile e fixture anonimizzate |
| O06 | Implementazione lock/aperture sicure Linux | F2 | Race test subprocess e symlink |
| O07 | Trasporto, DNS e proxy consentiti | F2/F3 | Test prima della connessione e redirect |

Risolvere le scelte entro il gate, senza richiedere al committente dettagli implementativi ordinari; chiedere chiarimenti soltanto quando cambia un requisito o serve un accesso non disponibile.

## Scheda difetto

```text
ID / severità / requisito:
Riproduzione senza segreti:
Atteso / osservato:
Impatto dati/sicurezza:
Correzione e test regressione:
Evidenza di chiusura:
```

## Scheda prova reale

```text
OS / Python / Tk / keyring:
Data / versione:
Account anonimizzato / corso autorizzato:
Operazioni limitate:
Confronto manuale browser:
Contenuti non verificabili:
Report/manifest redatti:
Esito / limiti:
```

Mai incollare password, cookie, token, voti o risposte personali nei registri. Eventuali evidenze private fuori dai documenti versionati.
