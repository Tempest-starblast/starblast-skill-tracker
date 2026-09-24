# -*- coding: utf-8 -*-
"""La pagina Info in italiano. L'originale è info_text_en.py."""

TITLE = "Info"
SUB = "Come funziona questo sito, in breve."
SEARCH = "Cerca in questa pagina…"
NOMATCH = "Niente in questa pagina corrisponde."
STALE = ()
FOOT = 'Domande? Chiedi a [[CONTACT]] su Discord.'

CARDS = [
 ("Che cos'è",
  '<p class="lead">Una classifica di abilità per la modalità a squadre di Starblast. Gioca partite a squadre, vinci e il tuo punteggio sale. Niente da installare e nessuna registrazione &mdash; sei in classifica appena giochi una partita che valutiamo.</p>'),

 ('Per iniziare',
  '<ol><li>Apri la scheda <a href="/play">Gioca</a> e scegli una partita.</li>'
  '<li>Premi <b>Gioca</b>. Il tuo nome viene copiato, pronto da incollare in Starblast.</li>'
  '<li>Gioca. Quando la partita finisce, il risultato compare qui entro una decina di minuti.</li>'
  '</ol>'
  '<p>Non serve altro. Accedere è facoltativo e serve solo per gli extra qui sotto.</p>'),

 ('Quali partite contano',
  '<p>Ogni partita a squadre dal vivo viene seguita, dal momento in cui appare la stanza. Non c’è un limite a quante insieme né un minimo di giocatori perché una stanza venga presa.</p>'
  '<p>Per essere <b>valutata</b>, una partita deve durare <b>almeno dieci minuti</b>. Quelle più brevi vengono comunque registrate e si possono rivedere, ma non cambiano il punteggio di nessuno.</p>'
  '<p>In una partita valutata viene valutato <b>chiunque</b> ci sia stato per <b>dieci minuti</b> e abbia raggiunto il punteggio minimo, che vinca o perda. Conta solo il tempo che l’osservatore ha visto.</p>'
  '<p>La scheda <a href="/play">Gioca</a> elenca ogni partita dal vivo e se l’osservatore c’è già; una stanza nuova viene presa in pochi secondi. Se una partita è dal vivo, conta.</p>'
  '<p>Il tempo che passi in partite valutate si somma sul tuo profilo &mdash; in totale, con le ultime due settimane accanto. Lo misura l’osservatore, quindi segue le stesse regole di tutto il resto: una partita non valutata, o una stanza che nessuno seguiva, non conta. Il conteggio è iniziato il 21 settembre 2026.</p>'),

 ('Il tuo punteggio',
  '<p>Tutti partono da <b>[[ELO]]</b>. Nelle tue prime <b>[[NEWGAMES]]</b> partite una sola partita può spostarti fino a <b>[[KNEW]]</b> punti, così trovi in fretta il tuo livello; dopo, fino a <b>[[KEST]]</b>.</p>'
  '<p>Quanto ti sposti dipende da chi batti. Battere uno schieramento più forte vale quasi il massimo; batterne uno molto più debole non vale quasi niente. Perdere funziona allo stesso modo, al contrario.</p>'
  '<p>La forza di una squadra è la media di tutti i suoi membri, quindi battere squadre deboli non ti farà salire &mdash; salire vuol dire battere giocatori che hanno a loro volta un punteggio alto. Conta anche chi ti sta accanto: la tua variazione mescola il tuo punteggio con la media della tua squadra, quindi portare compagni deboli alla vittoria vale più della stessa vittoria in una squadra fortissima &mdash; e perdere accanto a compagni deboli costa meno.</p>'),

 ('Piena e metà',
  '<p>Poiché l’osservatore segue ogni partita dall’inizio, vede esattamente quando la tua nave si è unita allo schieramento che poi ha vinto. Se ti sei unito nella prima metà della partita, la vittoria vale <b>per intero</b>. Nella seconda metà vale <b>al massimo la metà</b> &mdash; meno, quanto meno della partita hai visto.</p>'
  '<p>Una sconfitta vale sempre per intero: arrivare tardi non è un modo per perdere meno. Conta quando sei entrato davvero, non quando hai premuto Gioca.</p>'),

 ('Regole da sapere',
  '<p><b>Serve un punteggio, non solo un posto.</b> Per essere valutato devi aver raggiunto <b>[[MINPEAK]]</b> in qualche momento della partita se il tuo schieramento ha vinto, o <b>[[MINLOSE]]</b> se ha perso. Stare in una stanza non è giocare.</p>'
  '<p><b>Andarsene prima non evita una sconfitta.</b> Viene addebitata a tutti quelli che hanno giocato per lo schieramento perdente, che fossero ancora lì alla fine o no.</p>'
  '<p><b>Abbandonare uno schieramento che sembra battuto non ti dà la sua rimonta.</b> Se il tuo schieramento aveva meno del 25% di probabilità quando te ne sei andato, ed eri ancora via quando ha vinto, più di dieci minuti dopo, la vittoria non è tua. La tua pagina account lo spiega.</p>'),

 ("Due nomi",
  '<p><b>Il tuo nome account</b> è la riga della classifica che ti appartiene. Lì vive il'
  ' tuo punteggio, e non cambia se ti rinomini nel gioco. Si imposta in <a'
  ' href="/settings">Impostazioni</a>.</p><p><b>Il tuo nome di gioco</b> è come ti chiami in'
  ' Starblast in questo momento. Si imposta nella pagina <a href="/play">Gioca</a>, e puoi'
  ' cambiarlo quanto vuoi &mdash; è da quello che riconosciamo la tua nave in una lobby, e'
  ' una partita giocata con quel nome conta per il tuo account.</p><p>All&#39;inizio sono lo'
  ' stesso, e per la maggior parte delle persone lo restano. Differiscono solo se giochi con'
  ' un altro nome per un po&#39;.</p>'),

 ("La registrazione prima della partita, e la spunta verde",
  '<p>Premere <b>Gioca</b> prima di una partita è ciò che lega i due nomi. Il sito cerca in'
  ' quella lobby una nave che porta il tuo <b>nome di gioco</b>, decide che quella nave sei'
  ' tu, e mette il risultato sul tuo <b>nome account</b> &mdash; così il tuo punteggio'
  ' cresce in un posto solo, comunque tu ti chiami nel gioco.</p><p>Tieni quindi il nome di'
  ' gioco della pagina Gioca uguale a quello della tua nave. È quello che deve coincidere;'
  ' il nome account no.</p><p><b>Se non ti registri prima</b>, una partita con il tuo nome'
  ' di gioco conta comunque per te. Quello che la registrazione aggiunge è la prova di quale'
  ' nave fosse la tua: se qualcun altro vola con il tuo nome nella stessa lobby, la partita'
  ' viene trattenuta a meno che tu non ti sia registrato, e la <b>Protezione</b> conta solo'
  ' le partite per cui ti sei registrato. Un nome di gioco rivendicato da due account non'
  ' conta per nessuno dei due.</p><p>Una <b>&#10003;</b> accanto a un nome vuol dire che'
  ' quel giocatore ha la Protezione attiva: gli contano solo le partite per cui si è'
  ' registrato. È una valutazione più severa e più lenta, ed è facoltativa &mdash; si trova'
  ' in <a href="/settings">Impostazioni</a>.</p>'),

 ("Clan",
  '<p>Un clan è un gruppo di giocatori che condividono un tag. La sua pagina mostra la rosa'
  ' ordinata per abilità, il record complessivo, le sue vittorie in survival e dove gioca il'
  ' clan.</p><p><b>Come entrare.</b> <a href="/social">Social</a> ti suggerisce i clan i cui'
  ' membri giocano più o meno al tuo livello, e ti mostra tutti quelli che accettano'
  ' richieste. Puoi anche aprire la pagina di un clan e premere <b>Chiedi di entrare</b>,'
  ' oppure usare un link d&#39;invito che ti dà il suo leader. In entrambi i casi decide il'
  ' leader. Se il tuo nome nel gioco porta già il tag del clan quando il clan viene creato,'
  ' vieni aggiunto automaticamente.</p><p><b>Il tuo tag è mostrato esattamente com&#39;è'
  ' scritto</b> &mdash; lettere strane comprese. La versione in lettere semplici serve solo'
  ' dietro le quinte, così ogni modo di scrivere un tag conta come un unico clan e la'
  ' ricerca funziona in entrambi i versi. Un leader può aggiungere altri modi di scrivere il'
  ' tag in <a href="/myclan">Il tuo clan</a>, e ogni membro sceglie quale portare in <a'
  ' href="/account">Il tuo account</a>.</p><p><b>Una partita con il tag del tuo clan conta'
  ' per te</b>, in qualunque modo il tag sia scritto. Solo i membri di quel clan vengono'
  ' riconosciuti così, e ciò che segue il tag deve essere il tuo nome.</p><p><b>Il tuo nome'
  ' account sei solo tu.</b> Quando entri in un clan, il tag esce dal tuo nome account e'
  ' compare accanto come badge, così il tag può cambiare, e anche il tuo clan, senza che il'
  ' tuo record si sposti. La pagina dell&#39;account chiede conferma prima di salvare un'
  ' nome che porta un tag.</p><p><b>Ruoli.</b> Un leader può nominare co-leader e'
  ' moderatori. Un moderatore rimuove i membri semplici; un co-leader fa tutto quello che fa'
  ' il leader tranne eliminare il clan o toccare un altro co-leader. Nessuno può rimuovere'
  ' qualcuno del proprio ruolo o superiore.</p>'),

 ('Un nome già presente in classifica',
  '<p>Scrivilo nelle <a href="/settings">Impostazioni</a> e, se non è di nessuno, è subito tuo. Se ha già uno storico, la pagina ti propone invece di <b>rivendicarlo</b>. Dimostra che è tuo giocando una partita classificata di Deathmatch &mdash; il comando <b>/proveclaim</b> del bot Discord ti guida &mdash; oppure aspetta che [[CONTACT]] la esamini. Finché una rivendicazione è aperta compare sulla pagina di quel giocatore, così il vero proprietario può segnalarla.</p>'
  '<p>Lo stesso succede se un nome già in classifica <b>si legge</b> come quello che hai scritto &mdash; un nome semplice contro una versione con lettere decorate. È lì che stanno arrivando le tue partite, quindi ti viene proposta quella riga. Se è davvero un’altra persona, salva comunque il tuo nome.</p>'),

 ("Gestire un clan",
  '<p>I clan si assegnano a mano. Chiedilo nella pagina <a href="/clans">Clan</a> e'
  ' [[CONTACT]] approva o rifiuta su Discord. Se ti rifiutano, puoi richiedere di nuovo.</p>'
  '<p>Una volta approvato rivendichi il tuo tag, e compare una scheda <b>Il tuo clan</b>'
  ' con tutto in un posto solo: il link d&#39;invito, chi aspetta di entrare, la rosa, i'
  ' ruoli, la regione e l&#39;eliminazione del clan.</p>'),

 ("Lingue",
  '<p>Scegli una lingua nell&#39;intestazione di qualsiasi pagina &mdash; English, Español,'
  ' Français, Deutsch, Italiano, Русский, Tiếng Việt o 中文. Tutto il sito è tradotto,'
  ' questa pagina compresa. L&#39;inglese è l&#39;originale: se una traduzione suona'
  ' strana, è lì che sta il significato.</p>'),

 ("Discord",
  '<p>Il bot fa quasi tutto quello che fa questo sito &mdash; classifiche, il tuo profilo,'
  ' i clan, le richieste e i ruoli. Chiedi un invito a [[CONTACT]], poi usa <b>/help</b>'
  ' per vedere i comandi.</p>'),

 ("Cosa sappiamo di te",
  '<p><b>Non viene salvato nessun indirizzo IP.</b> Né quando visiti il sito, né quando'
  ' premi Gioca, né quando accedi.</p>'
  '<p>Accedere con Discord ci dà il tuo id account e il tuo nome utente. Google dà un id'
  ' account. Questo è tutto &mdash; nessuna email e niente con cui contattarti.</p>'
  '<p>Il codice del sito è pubblico, quindi tutto questo si può verificare invece di'
  ' crederci sulla parola.</p>'),

 ('Domande frequenti',
  '<div class="qa"><b>Ho vinto ma non è successo niente.</b> I risultati arrivano circa dieci minuti dopo la fine della partita. Se passa più tempo, di solito è una di queste cose: la partita è durata meno di dieci minuti, non ci sei stato per i dieci minuti necessari, il tuo punteggio non ha raggiunto il minimo, oppure hai lasciato il tuo schieramento mentre perdeva ed eri ancora via quando ha vinto.<b>Il mio nome compare due volte.</b> Una grafia diversa conta come un altro giocatore, perché è tutto ciò che il gioco comunica. Rivendica quello che usi davvero.<b>La classifica è stata azzerata.</b> I punteggi sono ancora in prova e potrebbero essere cancellati di nuovo. Niente di ciò che fai va perso; la classifica riparte semplicemente da capo.<b>Qualcosa non torna.</b> Dillo su <a href="/reports">Segnala</a> o avvisa [[CONTACT]] su Discord. Lo legge una persona.</div>'),
 ("Divisioni",
  '<p>La tua divisione è la tua posizione fra tutti i giocatori classificati della classifica generale, non un punteggio: cambia quindi quando si muovono i giocatori intorno a te. I giocatori ancora alle prime partite non vengono contati.</p>'
  '[[RANKS]]'),
]
