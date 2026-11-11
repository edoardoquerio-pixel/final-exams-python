# 24 - Controllo dei quiz senza revisione, 9 novembre 2026

Richiesta: controllare i 23 quiz segnalati senza un tentativo completato e revisionabile.
**Risultato attuale: uno ora espone una revisione valida, i restanti sono 22.**
Non sono stati avviati, continuati o inviati tentativi. Nessuna modifica al runtime
effettuata in questo controllo: non è emersa una revisione accessibile ignorata dal parser.

## Metodo e risultati

Login reale; lettura delle attività dei 32 corsi e delle **47 pagine quiz** individuate.
Ogni pagina è stata confrontata con il risultato di `Moodle.expand`, esaminando in
modo separato stato del tentativo, link/form di revisione, messaggi e condizioni di accesso.
I documenti sono stati acquisiti tramite GET; nessun pulsante di avvio è stato premuto.
Logout riuscito. Le date di consegna, i valori delle restrizioni sul profilo e altri
dati personali non sono riprodotti in questo report.

| Stato osservato | Quiz |
|---|---:|
| Collegamento di revisione riconosciuto dall'app | 25 |
| Tentativi completati, colonna Revisione: «Non permesso» | 6 |
| Accesso riservato attraverso condizioni sul profilo | 6 |
| Nessuna cronologia dei tentativi consultabile sulla pagina | 10 |
| Totale | 47 |

La dicitura «nessuna cronologia visibile» non dimostra che non sia mai stato svolto
un tentativo: descrive ciò che il sito rende consultabile all'account corrente.
Fra questi 10 casi: 8 quiz chiusi, 1 con vincolo Safe Exam Browser e senza riepilogo
visibile, 1 con pulsante di avvio disponibile e senza riepilogo. Alcuni quiz chiusi
richiedono anche Safe Exam Browser o una password d'accesso.

Nei 6 quiz completati risultano complessivamente 7 righe di tentativo completato:
un quiz ha due tentativi, entrambi con revisione non permessa. Nessun collegamento
o form di revisione presente in questi casi. Non è il parser a scartare un link valido.

## Verifica ora disponibile

L'attività [60603](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=60603), che nella
scansione precedente produceva l'avviso, ora espone un tentativo completato revisionabile.
Confermata la differenza confrontando le attività con il catalogo del check 22.

Esportazione eseguita con il downloader dell'app in un workspace isolato:
1 revisione scaricata, 5 file controllati (HTML e quattro allegati), 0 problemi,
logout riuscito. L'app la rileva normalmente a una nuova scansione.
Non è stato stabilito perché la disponibilità sia cambiata rispetto alla prova precedente.

## Dettaglio dei 22 casi ancora senza revisione

Gli identificativi di corso indicano il corso in cui è stato trovato il collegamento;
i valori delle condizioni personali non sono riportati.

### Completati, revisione non permessa

| Corso ID | Quiz |
|---|---|
| 2208 | [59855](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=59855) |
| 2213 | [48663](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=48663) |
| 2215 | [54762](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=54762) |
| 2229 | [52926](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=52926) |
| 2233 | [52629](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=52629) |
| 2234 | [58743](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=58743) |

### Riservati tramite condizioni sul profilo

| Corso ID | Quiz |
|---|---|
| 2216 | [51406](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=51406) |
| 2230 | [59272](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=59272), [60389](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=60389), [60575](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=60575) |
| 2231 | [58260](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=58260) |
| 2235 | [59779](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=59779) |

### Nessuna cronologia dei tentativi consultabile

| Corso ID | Quiz | Condizione osservata |
|---|---|---|
| 2223 | [56111](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=56111) | Avvio disponibile, non eseguito |
| 2223 | [58888](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=58888) | Safe Exam Browser richiesto |
| 2224 | [55190](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=55190), [55194](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=55194) | Quiz chiusi |
| 2225 | [58327](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=58327), [58990](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=58990) | Chiusi, password e Safe Exam Browser |
| 2231 | [57970](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=57970) | Chiuso, Safe Exam Browser |
| 2233 | [59598](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=59598), [59635](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=59635), [59608](https://fad.its-ictpiemonte.it/mod/quiz/view.php?id=59608) | Chiusi, Safe Exam Browser |

## Limiti e evidenze

I 25 link riconosciuti non sono stati tutti nuovamente esportati: la nuova revisione
è stata provata end-to-end, le altre pagine sono state confrontate con il parser.
Non è stato ripetuto il censimento visivo browser: si tratta di letture autenticate
delle pagine reali e di un controllo strutturale dell'HTML restituito.

Evidenze in `app/.verification-quiz-reviews-20261109/`, ignorata da Git:
summary e classificazione, pagine e dettagli privati, risultato e workspace dell'export.
Non includere pagine private, dati personali o risposte nei commit.
Il report non richiede di ignorare automaticamente questi 22 quiz: la precedente
esclusione dei corsi non disponibili resta una regola distinta.
