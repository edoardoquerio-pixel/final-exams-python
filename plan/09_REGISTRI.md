# 09 - Registri operativi

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
