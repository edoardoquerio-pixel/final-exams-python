# Piano di realizzazione - FAD Downloader

Ultimo esito: [check completo del 9 novembre](22_CHECK_COMPLETO_2026_11_09.md).

**Per riprendere il lavoro leggere prima [00_CONTESTO_ATTUALE.md](00_CONTESTO_ATTUALE.md).**
Raccoglie lo stato al 9 novembre 2026, le istruzioni correnti dell'utente e le modifiche
ancora da verificare. Le sezioni iniziali di questo piano descrivono anche scelte storiche;
non sono un invito a ricominciare l'applicazione da zero. L'upload è attualmente rimandato.

Versione 1.2 - aggiornamento del 26 ottobre 2026. Termine indicativo: fine novembre 2026.

Questi documenti guidano l'evoluzione del progetto descritto nel PDF. L'applicazione corrente è la 0.2.0: non ricominciare da zero. Il [registro 0.0.1](12_VERSIONE_0_0_1.md) descrive la prima implementazione; il registro 18 riporta il gate di produzione corrente. Il precedente `tool/download_fad.py` non è una dipendenza.

## Ordine di lettura

Gate per la produzione Linux: [collaudo corrente](18_COLLAUDO_PRODUZIONE.md).

Ultimo confronto degli originali: [integrità rispetto alla FAD](19_INTEGRITA_FAD.md).

Ultimo controllo della completezza: [sito rispetto alla GUI](20_CONFRONTO_SITO_GUI.md).
Evidenzia 33 riferimenti a materiali didattici assenti dal catalogo corrente dell'app.

Ultimo aggiornamento operativo: [configurazione e collaudo](17_CONFIGURAZIONE_E_COLLAUDO.md).

Esiti più recenti: [verifiche del 26 ottobre 2026](15_VERIFICHE_2026_10_26.md).
Copertura corrente di ogni requisito: [audit R01–R28 e lista utente](16_AUDIT_REQUISITI.md).

1. [Requisiti e accettazione](01_REQUISITI.md)
2. [Architettura e dati](02_ARCHITETTURA.md)
3. [Fasi di implementazione](03_IMPLEMENTAZIONE.md)
4. [Sicurezza](04_SICUREZZA.md)
5. [Test e controlli indipendenti](05_TEST_E_VERIFICHE.md)
6. [GUI e flussi](06_GUI_E_FLUSSI.md)
7. [Lavoro con AI e prompt](07_WORKFLOW_AI.md)
8. [GNU/Linux e rilascio](08_LINUX_E_RILASCIO.md)
9. [Registri operativi](09_REGISTRI.md)
10. [Matrice requisiti, fasi e test](10_TRACCIABILITA.md)
11. [Esito della revisione e questioni aperte](11_REVISIONE.md)
12. [Implementazione e collaudo della versione 0.0.1](12_VERSIONE_0_0_1.md)
13. [Versione 0.1.0 e copertura dei requisiti](13_VERSIONE_0_1_0.md)
14. [SQLite, utenti DB e report PDF — versione 0.2.0](14_DATABASE_UTENTI_PDF.md)

## Regole comuni

- Sviluppare nella sottocartella `app/` di questo progetto, senza modificare esercizi, Terraform o altri progetti.
- GUI completa e CLI facoltativa, con servizi condivisi.
- Solo contenuti visibili all'account; nessun invio di quiz, consegne o modifiche ai corsi.
- Credenziali reali nel `.env` locale o nei campi dell'applicazione, secondo R03 aggiornato; mai in prompt AI, log, fixture o commit. Il portachiavi non è usato dal login corrente.
- Test automatici senza rete esterna per default; prove reali deliberate su account e corso autorizzati.
- Nessuna pubblicazione, upload o invio a terzi incluso automaticamente nel piano.
- Ogni requisito completato deve avere un'evidenza. Una verifica non eseguita resta «non eseguita».

## Stato iniziale

È disponibile una versione sperimentale in `app/`. Le fasi del piano finale rimangono aperte fino al superamento dei rispettivi criteri; lo stato effettivo è nel registro 0.0.1. Il PDF rimane la proposta da presentare; questa cartella contiene il piano tecnico interno.

La revisione documentale 1.1 è completata; non equivale a validazione del software o della compatibilità Moodle. Le scelte quantitative sono obiettivi iniziali da misurare. Non si promette supporto universale a temi Moodle, plugin quiz o distribuzioni Linux.

## Come usare il piano

Prima leggere l'esito della revisione, poi iniziare da F0. La matrice collega ogni requisito a un responsabile tecnico, una fase e una prova. Un campo implementativo ancora aperto va risolto nel gate indicato, senza inventare un comportamento durante lo sviluppo. Per i contratti usare 01 e 02; per i controlli 04 e 05; 09 raccoglie le evidenze. Le modifiche devono restare coerenti tra questi documenti.
