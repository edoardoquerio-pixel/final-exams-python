# 10 - Matrice di copertura

Questa matrice descrive il piano iniziale. Per lo stato corrente, inclusi R26–R28,
consultare [16_AUDIT_REQUISITI.md](16_AUDIT_REQUISITI.md); le righe keyring sono storiche.

Ogni riga richiede codice, test e prova di accettazione prima della chiusura. Le famiglie T01-T12 sono definite in [05_TEST_E_VERIFICHE.md](05_TEST_E_VERIFICHE.md). Stato iniziale per tutte le righe: **da implementare e verificare**.

| Requisito | Fase | Componente | Test | Evidenza di accettazione |
|---|---|---|---|---|
| R01 | F0A, F11 | Packaging/GUI | T01, T08 | Installazione Ubuntu e avvio desktop |
| R02 | F3 | AuthService | T02, T10 | Login/logout/errore e sessione scaduta |
| R03 | F3 | env_config/GUI | T02 | `.env` autorevole, salvataggio solo dopo successo, ricaricamento/cancellazione e account isolati |
| R04 | F4 | CatalogAdapter | T03 | Catalogo confrontato con browser |
| R05 | F4, F5 | Mapping/Planner | T03, T04 | Rescan conserva decisioni e distingue novità |
| R06 | F5, F9 | Planner/GUI | T04, T08 | Selezione gerarchica coincide con piano |
| R07 | F5, F8 | Planner/quiz | T04, T07 | Filtri materiali/test e contenuti risultanti |
| R08 | F2, F5 | Template/Planner | T04, T10 | Anteprima e percorsi effettivi uguali |
| R09 | F6 | TransferService | T05, T10 | File/cartelle confrontati e integri |
| R10 | F7 | ExportService | T06, T10 | Capitoli/asset completi e link locali |
| R11 | F0A, F8 | Quiz adapter/export | T07, T10 | Risposte visibili e tentativi corretti, nessun invio |
| R12 | F6 | Transfer/State | T05, T11 | Aggiornamenti e verificatore indipendente |
| R13 | F3, F9 | Auth/orchestrator | T02, T08 | Ripresa stesso account e piano |
| R14 | F5, F9 | GUI/worker | T04, T08, T12 | Reattività, annulla, dry-run senza scritture |
| R15 | F10 | ReportService | T09 | Conti coerenti e retry mirato |
| R16 | F10 | Index builder | T06, T09, T10 | Link funzionanti senza contenuti attivi |
| R17 | F10, F11 | CLI | T01, T09 | Parità con GUI e codici di uscita |
| R18 | F9, F10 | GUI/indice locale | T09 | Uso offline senza login/rete |
| R19 | F5, F6 | Planner/commit | T04, T05 | Conflitti preservati; assenza remota non distruttiva |
| R20 | F7, F8 | Export generations | T06, T11 | Crash non rompe la generazione precedente |
| R21 | F0A, F6, F9 | HTTP/worker | T08, T12 | Limiti e tempi misurati sul sistema di riferimento |
| R22 | F1, F11 | Config/packaging | T01, T11 | XDG, precedenza e wheel fuori repository |
| R23 | F2, F3, F7, F8 | Policy e sanitizer | T07, T10 | Input avversi respinti prima degli effetti |
| R24 | F10 | Risultati/report/verificatore | T05, T09 | Task riconciliati e hash verificati separatamente |
| R25 | F6, F11 | StateRepository | T11 | Migrazione/rollback e cleanup controllato |

## Copertura della proposta

Il PDF richiede oggetto, scopo, modalità operative e termine complessivo: questi piani dettagliano le modalità senza introdurre un servizio cloud o sostituire la GUI. R18-R25 rendono verificabili comportamenti impliciti della consultazione locale, sicurezza e affidabilità. Non costituiscono funzioni commerciali aggiuntive né certificazioni di conformità.

## Regola di chiusura

Ogni evidenza deve riportare ambiente e versione, comando o procedura, risultato atteso/osservato e limiti. Un test sintetico certifica solo quel contratto; non dimostra compatibilità col tema reale. Per i casi non disponibili sul sito registrare il gap, senza dichiarare l'intera funzione verificata.
