# -*- coding: utf-8 -*-
"""Die Info-Seite auf Deutsch. Das Original ist info_text_en.py."""

TITLE = "Info"
SUB = "Wie diese Seite funktioniert, kurz gefasst."
FOOT = 'Fragen? Frag [[CONTACT]] auf Discord.'

CARDS = [
 ("Worum es geht",
  '<p class="lead">Eine Stärkewertung für den Teammodus von Starblast. Spiel Teamspiele,'
  ' gewinn, und deine Wertung steigt. Nichts zu installieren und nichts anzumelden'
  ' &mdash; du stehst in der Rangliste, sobald du ein Spiel gewinnst, das wir gerade'
  ' beobachten.</p>'),

 ("Erste Schritte",
  '<ol>'
  '<li>Öffne den Reiter <a href="/play">Spielen</a> und wähle ein Spiel, das als beobachtet'
  ' markiert ist.</li>'
  '<li>Drück <b>Spielen</b>. Dein Name wird kopiert, fertig zum Einfügen in Starblast.</li>'
  '<li>Spiel das Spiel. Wenn es endet, erscheint das Ergebnis hier innerhalb einer'
  ' Minute.</li>'
  '</ol>'
  '<p>Mehr ist nicht nötig. Anmelden ist freiwillig und nur für die Extras weiter unten'
  ' gedacht.</p>'),

 ("Welche Spiele zählen",
  '<p>Wir können immer nur ein paar Spiele gleichzeitig beobachten, also zählt nicht jedes.'
  ' Ein Spiel ist beobachtbar, sobald es <b>20 Minuten alt</b> ist, bis es 90 Minuten alt'
  ' ist, und es braucht mindestens vier Spieler.</p>'
  '<p>Der Reiter <a href="/play">Spielen</a> zeigt genau, welche Lobbys gerade beobachtet'
  ' werden. Steht ein Spiel nicht auf der Liste, wird nichts davon erfasst &mdash; es kommt'
  ' auch später nicht an.</p>'),

 ("Deine Wertung",
  '<p>Alle starten bei <b>[[ELO]]</b>. Ein Spiel bewegt dich um höchstens <b>[[K]]</b>'
  ' Punkte.</p>'
  '<p>Wie weit es dich bewegt, hängt davon ab, wen du schlägst. Eine stärkere Seite zu'
  ' schlagen bringt fast das Maximum; eine viel schwächere zu schlagen bringt fast nichts.'
  ' Verlieren funktioniert genauso, nur andersherum. Zwei gleich starke Teams bewegen sich'
  ' um genau einen Punkt.</p>'
  '<p>Die Stärke eines Teams ist der Durchschnitt aller seiner Spieler. Schwache'
  ' Teams abzufarmen bringt dich also nicht nach oben &mdash; aufsteigen heißt Leute zu'
  ' schlagen, die selbst hoch bewertet sind.</p>'),

 ("Ganz und halb",
  '<p>Warst du schon im Spiel, als wir angefangen haben zu beobachten, zählt es ganz.'
  ' Steigst du in ein Spiel ein, das bereits beobachtet wird, zählt es trotzdem, nämlich'
  ' <b>halb</b> &mdash; für Gewinner wie Verlierer gleichermaßen. Der Reiter Spielen sagt'
  ' vorher, was was ist.</p>'),

 ("Zwei Regeln, die man kennen sollte",
  '<p><b>Früh gehen erspart die Niederlage nicht.</b> Ein verlierendes Team wird mit seiner'
  ' vollsten Aufstellung belastet, nicht mit denen, die am Ende noch da waren.</p>'
  '<p><b>Ein Punktestand unter [[MINSCORE]] wird überhaupt nicht gewertet</b>, ob Sieg oder'
  ' Niederlage. In einer Lobby zu sitzen ist kein Spielen.</p>'),

 ("Zwei Namen",
  '<p><b>Dein Kontoname</b> ist die Zeile in der Rangliste, die dir gehört. Dort lebt deine'
  ' Wertung, und sie ändert sich nicht, wenn du dich im Spiel umbenennst. Einzustellen in'
  ' den <a href="/settings">Einstellungen</a>.</p>'
  '<p><b>Dein Spielname</b> ist das, wie du in Starblast gerade heißt. Einzustellen auf der'
  ' Seite <a href="/play">Spielen</a>, und so oft zu ändern, wie du magst &mdash; damit'
  ' erkennen wir dein Schiff in einer Lobby, mehr nicht.</p>'
  '<p>Am Anfang sind beide gleich, und bei den meisten bleiben sie es. Sie unterscheiden'
  ' sich nur, wenn du eine Weile unter etwas anderem spielst.</p>'),

 ("Anmelden vor dem Spiel, und der grüne Haken",
  '<p><b>Spielen</b> zu drücken, bevor ein Spiel losgeht, verbindet die beiden Namen. Die'
  ' Seite hält in dieser Lobby nach einem Schiff mit deinem <b>Spielnamen</b> Ausschau,'
  ' entscheidet, dass dieses Schiff du bist, und schreibt das Ergebnis deinem'
  ' <b>Kontonamen</b> gut &mdash; so wächst deine Wertung an einer Stelle, egal wie du im'
  ' Spiel heißt.</p>'
  '<p>Halte also den Spielnamen auf der Seite Spielen gleich dem Namen deines Schiffs. Der'
  ' muss übereinstimmen; dein Kontoname nicht.</p>'
  '<p><b>Meldest du dich nicht an</b>, landet das Ergebnis einfach auf dem Namen, den das'
  ' Spiel gemeldet hat. Für dich zählt das nur, wenn dieser Name dir gehört.</p>'
  '<p>Ein <b>&#10003;</b> neben einem Namen heißt, dass dieser Spieler den Schutz'
  ' eingeschaltet hat: Für ihn zählen nur Spiele, für die er sich angemeldet hat. Das ist'
  ' eine strengere, langsamere Wertung, und sie ist freiwillig &mdash; zu finden in den'
  ' <a href="/settings">Einstellungen</a>.</p>'),

 ("Clans",
  '<p>Ein Clan ist eine Gruppe von Spielern, die sich ein Kürzel teilen. Seine Seite zeigt'
  ' die nach Stärke sortierte Mannschaft, die gemeinsame Bilanz und wo der Clan spielt.</p>'
  '<p><b>Beitreten.</b> Öffne die Seite des Clans und drück <b>Beitritt anfragen</b>, oder'
  ' nutze einen Einladungslink, den dir sein Anführer gibt. So oder so entscheidet der'
  ' Anführer. Trägt dein Spielname das Kürzel des Clans schon, wenn der Clan angelegt wird,'
  ' wirst du automatisch aufgenommen.</p>'
  '<p><b>Dein Kürzel wird genau so angezeigt, wie es geschrieben ist</b> &mdash; samt'
  ' Zierbuchstaben. Die Fassung in einfachen Buchstaben wird nur hinter den Kulissen'
  ' benutzt, damit jede Schreibweise eines Kürzels als ein Clan zählt und die Suche in'
  ' beide Richtungen funktioniert.</p>'
  '<p><b>Ränge.</b> Ein Anführer kann Co-Anführer und Moderatoren ernennen. Ein Moderator'
  ' entfernt normale Mitglieder; ein Co-Anführer kann alles, was der Anführer kann, außer'
  ' den Clan zu löschen oder einen anderen Co-Anführer anzufassen. Niemand kann jemanden'
  ' des eigenen Rangs oder darüber entfernen.</p>'),

 ("Ein Name, der schon in der Rangliste steht",
  '<p>Tipp ihn in den <a href="/settings">Einstellungen</a> ein: Gehört er niemandem, ist'
  ' er sofort deiner. Hat er schon eine Bilanz, bietet die Seite stattdessen an, ihn zu'
  ' <b>beanspruchen</b>: Er wird deiner, sobald dieser Name das nächste Mal ein beobachtetes'
  ' Spiel gewinnt. So wissen wir, dass du es wirklich bist und nicht jemand, der sich an'
  ' deiner Wertung bedient.</p>'
  '<p>Dasselbe passiert, wenn ein Name in der Rangliste sich <b>liest</b> wie der, den du'
  ' eingegeben hast &mdash; ein schlichter Name gegen eine Fassung mit Zierbuchstaben. Dort'
  ' landen deine Spiele, also wird dir diese Zeile angeboten. Ist es wirklich jemand'
  ' anderes, speichere deinen Namen trotzdem.</p>'),

 ("Einen Clan führen",
  '<p>Clans werden von Hand vergeben. Frag auf der Seite <a href="/clans">Clans</a>, und'
  ' [[CONTACT]] genehmigt oder lehnt auf Discord ab. Bei einer Ablehnung darfst du erneut'
  ' fragen.</p>'
  '<p>Nach der Genehmigung beanspruchst du dein Kürzel, und ein Reiter <b>Dein Clan</b>'
  ' erscheint, mit allem an einem Ort: Einladungslink, wer auf Aufnahme wartet, die'
  ' Mannschaft, Ränge, die Region und das Löschen des Clans.</p>'),

 ("Sprachen",
  '<p>Wähl oben auf jeder Seite eine Sprache &mdash; English, Español, Français, Deutsch,'
  ' Italiano, Русский, Tiếng Việt oder 中文. Die ganze Seite ist übersetzt, diese hier'
  ' eingeschlossen. Das Englische ist das Original: Liest sich eine Übersetzung einmal'
  ' schief, steht dort, was gemeint ist.</p>'),

 ("Discord",
  '<p>Der Bot kann fast alles, was diese Seite kann &mdash; Ranglisten, dein Profil, Clans,'
  ' Bewerbungen und Ränge. Frag [[CONTACT]] nach einer Einladung und nutz dann <b>/help</b>'
  ' für die Befehle.</p>'),

 ("Was wir über dich wissen",
  '<p><b>Es werden keine IP-Adressen gespeichert.</b> Nicht beim Besuch, nicht beim Drücken'
  ' von Spielen, nicht beim Anmelden.</p>'
  '<p>Die Anmeldung mit Discord gibt uns deine Konto-ID und deinen Namen. Google gibt eine'
  ' Konto-ID. Das ist alles &mdash; keine E-Mail und nichts, womit man dich erreichen'
  ' könnte.</p>'
  '<p>Der Code der Seite ist öffentlich, all das lässt sich also nachprüfen statt nur'
  ' glauben.</p>'),

 ("Häufige Fragen",
  '<div class="qa">'
  '<b>Ich habe gewonnen, und nichts ist passiert.</b>'
  ' Das Spiel war vermutlich keines der beobachteten. Der Reiter Spielen listet sie auf,'
  ' bevor du einsteigst.'
  '<b>Mein Name steht zweimal in der Rangliste.</b>'
  ' Eine andere Schreibweise zählt als anderer Spieler, denn mehr meldet das Spiel nicht.'
  ' Beanspruche den, unter dem du wirklich spielst.'
  '<b>Die Rangliste wurde zurückgesetzt.</b>'
  ' Die Wertungen werden noch getestet und können erneut gelöscht werden. Nichts, was du'
  ' tust, ist umsonst; die Rangliste fängt nur wieder von vorne an.'
  '<b>Da stimmt etwas nicht.</b>'
  ' Sag es unter <a href="/reports">Melden</a> oder sag [[CONTACT]] auf Discord Bescheid.'
  ' Das liest ein Mensch.'
  '</div>'),
]
