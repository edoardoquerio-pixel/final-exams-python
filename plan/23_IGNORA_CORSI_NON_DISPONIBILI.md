# 23 - Ignorare i link a corsi non disponibili agli studenti

9 novembre 2026. Richiesta esplicita dell'utente: ignorare i collegamenti che
restituiscono «Questo corso al momento non è disponibile agli studenti».

Il parser distingue ora questa risposta con il codice `COURSE_UNAVAILABLE`.
Durante la scansione il collegamento è saltato: nessuna risorsa aggiunta al catalogo,
nessun avviso aggiunto alla raccolta. Rimane solo un evento diagnostico senza titoli
o URL. Gli altri accessi negati, errori di rete e rifiuti della policy restano segnalati;
cancellazione e sessione scaduta continuano a interrompere la scansione.

Non esiste una blacklist di ID o URL: ogni nuova scansione controlla nuovamente la
risposta. Se il sito rende disponibile il materiale, l'app lo considera normalmente.
L'esclusione di questi riferimenti era già presente nei fatti; cambia la loro gestione
esplicita come elementi da ignorare, anziché avvisi da mostrare.

Verifica reale mirata sui 17 riferimenti storici, con elenco di attività fornito dal
precedente censimento e risposte di rete effettive: **15 ignorati**, **1 HTML valido
conservato**, **1 redirect esterno ancora segnalato**. Nessun avviso di indisponibilità,
logout riuscito. Non è stata ripetuta l'intera scansione di tutti i corsi.

Regressioni: esclusione senza avviso, prosecuzione delle risorse valide, mantenimento
degli altri errori e ricomparsa di una risorsa resa disponibile nella scansione successiva.
Le segnalazioni salvate nei vecchi cataloghi restano storiche: riavviare l'app aggiornata
e usare «Scansiona FAD» per ottenere il nuovo comportamento.

Linux 3.14/Xvfb e filesystem POSIX: 145 passati sui sorgenti e sulla wheel installata;
benchmark superato. Windows: 141 passati, 4 saltati per GUI e no-follow Linux; Ruff/Bandit/pip check,
build e smoke della wheel superati. Le evidenze di questo task sono in
`app/.verification-ignore-unavailable/`, ignorata da Git; non sono dati da pubblicare.
Modifiche locali, nessun commit o push eseguito.
