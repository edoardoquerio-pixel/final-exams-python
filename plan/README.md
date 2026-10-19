# Piano di realizzazione - FAD Downloader

Versione 1.1 - revisione del 14 ottobre 2026. Termine indicativo: fine novembre 2026.

Questi documenti guidano lo sviluppo da zero del progetto descritto nel PDF. La prima implementazione sperimentale è descritta nel [registro 0.0.1](12_VERSIONE_0_0_1.md), che distingue le prove superate dalle verifiche ancora da svolgere. Il precedente `tool/download_fad.py` non è una dipendenza; eventuali confronti vanno documentati.

## Ordine di lettura

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
- Credenziali reali soltanto nel prompt locale o nel portachiavi approvato; mai in prompt AI, log, fixture o commit.
- Test automatici senza rete esterna per default; prove reali deliberate su account e corso autorizzati.
- Nessuna pubblicazione, upload o invio a terzi incluso automaticamente nel piano.
- Ogni requisito completato deve avere un'evidenza. Una verifica non eseguita resta «non eseguita».

## Stato iniziale

È disponibile una versione sperimentale in `app/`. Le fasi del piano finale rimangono aperte fino al superamento dei rispettivi criteri; lo stato effettivo è nel registro 0.0.1. Il PDF rimane la proposta da presentare; questa cartella contiene il piano tecnico interno.

La revisione documentale 1.1 è completata; non equivale a validazione del software o della compatibilità Moodle. Le scelte quantitative sono obiettivi iniziali da misurare. Non si promette supporto universale a temi Moodle, plugin quiz o distribuzioni Linux.

## Come usare il piano

Prima leggere l'esito della revisione, poi iniziare da F0. La matrice collega ogni requisito a un responsabile tecnico, una fase e una prova. Un campo implementativo ancora aperto va risolto nel gate indicato, senza inventare un comportamento durante lo sviluppo. Per i contratti usare 01 e 02; per i controlli 04 e 05; 09 raccoglie le evidenze. Le modifiche devono restare coerenti tra questi documenti.
