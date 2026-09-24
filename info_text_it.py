# -*- coding: utf-8 -*-
"""La pagina Info in italiano. L'originale è info_text_en.py."""

TITLE = "Info"
SUB = "Come funziona questo sito, in breve."
SEARCH = "Cerca in questa pagina…"
NOMATCH = "Niente in questa pagina corrisponde."
# Card 2 (which games count) states rules that changed on 16 Sep 2026:
# no player minimum, a ten-minute match, top eight per team. Until this
# file is retranslated the page shows the English card there.
STALE = (2, 14)   # 9.74.0: no top-eight cap - English until retranslated
FOOT = 'Domande? Chiedi a [[CONTACT]] su Discord.'

CARDS = [
 ("Che cos'è",
  '<p class="lead">Una classifica di abilità per la modalità a squadre di Starblast. Gioca'
  ' partite a squadre, vinci, e il tuo punteggio sale. Niente da installare e niente'
  ' iscrizioni &mdash; sei in classifica appena vinci una partita che stiamo'
  ' osservando.</p>'),

 ("Per iniziare",
  '<ol>'
  '<li>Apri la scheda <a href="/play">Gioca</a> e scegli una partita segnata come'
  ' osservata.</li>'
  '<li>Premi <b>Gioca</b>. Il tuo nome viene copiato, pronto da incollare in Starblast.</li>'
  '<li>Gioca la partita. Alla fine il risultato compare qui entro un minuto.</li>'
  '</ol>'
  '<p>Non serve altro. Accedere è facoltativo e serve solo per gli extra qui sotto.</p>'),

 ("Quali partite contano",
  '<p>Ogni partita a squadre dal vivo viene osservata, dal momento in cui la lobby compare.'
  ' Non c&#39;è un limite a quante alla volta né un minimo di giocatori perché una lobby'
  ' venga rilevata.</p><p>Per essere <b>valutata</b>, una partita deve durare <b>almeno'
  ' dieci minuti</b>. Quelle più corte vengono comunque registrate e si possono rivedere, ma'
  ' non muovono il punteggio di nessuno.</p><p>In una partita valutata, i giocatori valutati'
  ' sono gli <b>otto migliori per punteggio</b> di ogni squadra, e servono circa <b>dieci'
  ' minuti in partita</b> per essere tra loro &mdash; a un vincitore servono comunque, per'
  ' quanto presto sia arrivato.</p><p>La scheda <a href="/play">Gioca</a> elenca ogni'
  ' partita dal vivo e se l&#39;osservatore è già su di essa; una lobby appena creata viene'
  ' rilevata in pochi secondi. Se una partita è dal vivo, conta.</p>'
  '<p>Il tempo che passi nelle partite valide viene sommato sul tuo profilo &mdash; il totale di sempre, con le ultime due settimane accanto. Lo misura l&rsquo;osservatore, quindi valgono le stesse regole di sopra: una partita non valida, o una lobby che nessuno stava guardando, non conta nulla. Il conteggio è iniziato il 21 settembre 2026.</p>'),

 ("Il tuo punteggio",
  '<p>Si parte tutti da <b>[[ELO]]</b>. Una partita ti sposta al massimo di <b>[[K]]</b>'
  ' punti.</p>'
  '<p>Di quanto ti sposti dipende da chi batti. Battere una squadra più forte rende quasi'
  ' il massimo; batterne una molto più debole non rende quasi nulla. Perdere funziona allo'
  ' stesso modo, al contrario. Due squadre pari si spostano di esattamente un punto.</p>'
  '<p>La forza di una squadra è la media di tutti i suoi giocatori, quindi accanirsi'
  ' sulle squadre deboli non ti farà salire &mdash; salire vuol dire battere gente a sua'
  ' volta ben valutata. Conta anche chi hai accanto: la tua variazione fonde il tuo punteggio con la media della squadra &mdash; trascinare alleati deboli alla vittoria rende più della stessa vittoria in una squadra fortissima, e perdere con alleati deboli costa meno.</p>'),

 ("Piena e metà",
  '<p>Poiché l&#39;osservatore segue ogni partita fin dall&#39;inizio, vede esattamente'
  ' quando la tua nave è entrata. Gioca fin dall&#39;inizio e conti <b>piena</b>; entra in'
  ' una partita già bene avviata e conta a <b>metà</b> &mdash; per chi vince come per chi'
  ' perde. Si giudica in base a quando sei entrato davvero nella partita, non a quando premi'
  ' Gioca.</p>'),

 ("Due regole da sapere",
  '<p><b>Andarsene in anticipo non evita la sconfitta.</b> Una squadra che perde viene'
  ' addebitata con la sua formazione più completa, non con chi era ancora lì alla'
  ' fine.</p>'
  '<p><b>Un punteggio sotto [[MINSCORE]] non viene valutato affatto</b>, vinta o persa.'
  ' Stare fermi in una lobby non è giocare.</p>'),

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

 ("Un nome già presente in classifica",
  '<p>Scrivilo in <a href="/settings">Impostazioni</a> e, se non è di nessuno, è subito'
  ' tuo. Se ha già un record, la pagina propone invece di <b>rivendicarlo</b>: diventa tuo'
  ' la prossima volta che quel nome vince una partita osservata, ed è così che sappiamo che'
  ' sei davvero tu e non qualcuno che si serve del tuo punteggio.</p>'
  '<p>Lo stesso vale se un nome già in classifica <b>si legge</b> come quello che hai'
  ' scritto &mdash; un nome semplice contro una versione in lettere ornate. È lì che stanno'
  ' finendo le tue partite, quindi ti viene proposta quella riga. Se è davvero un&#39;altra'
  ' persona, salva comunque il tuo nome.</p>'),

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

 ("Domande frequenti",
  '<div class="qa">'
  '<b>Ho vinto e non è successo niente.</b>'
  ' Probabilmente la partita non era tra quelle osservate. La scheda Gioca le elenca prima'
  ' che tu entri.'
  '<b>Il mio nome è due volte in classifica.</b>'
  ' Una grafia diversa conta come un altro giocatore, perché è tutto quello che il gioco'
  ' riporta. Rivendica quello con cui giochi davvero.'
  '<b>La classifica è stata azzerata.</b>'
  ' I punteggi sono ancora in prova e potrebbero essere cancellati di nuovo. Niente di'
  ' quello che fai va perso; la classifica riparte e basta.'
  '<b>Qualcosa non torna.</b>'
  ' Dillo su <a href="/reports">Segnala</a> oppure scrivi a [[CONTACT]] su Discord. Lo'
  ' legge una persona.'
  '</div>'),
 ("Divisioni",
  '<p>La tua divisione è la tua posizione fra tutti i giocatori classificati della classifica generale, non un punteggio: cambia quindi quando si muovono i giocatori intorno a te. I giocatori ancora alle prime partite non vengono contati.</p>'
  '[[RANKS]]'),
]
