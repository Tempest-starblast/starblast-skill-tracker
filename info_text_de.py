# -*- coding: utf-8 -*-
"""Die Info-Seite auf Deutsch. Das Original ist info_text_en.py."""

TITLE = "Info"
SUB = "Wie diese Seite funktioniert, kurz gefasst."
SEARCH = "Diese Seite durchsuchen…"
NOMATCH = "Auf dieser Seite passt dazu nichts."
STALE = ()
FOOT = 'Fragen? Frag [[CONTACT]] auf Discord.'

CARDS = [
 ('Worum es geht',
  '<p class="lead">Eine Skill-Rangliste für den Team-Modus von Starblast. Spiel Teamspiele, gewinne, und deine Wertung steigt. Nichts zu installieren und keine Anmeldung nötig &mdash; du stehst in der Rangliste, sobald du ein Spiel spielst, das wir werten.</p>'),

 ('Erste Schritte',
  '<ol><li>Öffne den Tab <a href="/play">Spielen</a> und wähle ein Spiel.</li>'
  '<li>Drück <b>Spielen</b>. Dein Name wird kopiert und kann direkt in Starblast eingefügt werden.</li>'
  '<li>Spiel. Wenn das Spiel endet, erscheint das Ergebnis hier innerhalb von etwa zehn Minuten.</li>'
  '</ol>'
  '<p>Mehr ist nicht nötig. Anmelden ist freiwillig und nur für die Extras weiter unten gedacht.</p>'),

 ('Welche Spiele zählen',
  '<p>Jedes laufende Teamspiel wird beobachtet, ab dem Moment, in dem die Lobby erscheint. Es gibt keine Grenze, wie viele gleichzeitig, und keine Mindestzahl an Spielern, damit eine Lobby aufgenommen wird.</p>'
  '<p>Um <b>gewertet</b> zu werden, muss ein Spiel <b>mindestens zehn Minuten</b> laufen. Kürzere Spiele werden trotzdem aufgezeichnet und können angesehen werden, verändern aber niemandes Wertung.</p>'
  '<p>In einem gewerteten Spiel wird <b>jeder</b> gewertet, der <b>zehn Minuten</b> dabei war und die Mindestpunktzahl erreicht hat, ob Sieg oder Niederlage. Es zählt nur die Zeit, die der Beobachter gesehen hat.</p>'
  '<p>Der Tab <a href="/play">Spielen</a> zeigt jedes laufende Spiel und ob der Beobachter schon dabei ist; eine neue Lobby wird innerhalb weniger Sekunden aufgenommen. Wenn ein Spiel läuft, zählt es.</p>'
  '<p>Die Zeit, die du in gewerteten Spielen verbringst, wird in deinem Profil zusammengezählt &mdash; insgesamt und daneben die letzten zwei Wochen. Der Beobachter misst sie, also gelten dieselben Regeln wie oben: Ein ungewertetes Spiel oder eine Lobby, die niemand beobachtet hat, zählt nicht. Die Zählung begann am 21. September 2026.</p>'),

 ('Deine Wertung',
  '<p>Alle starten bei <b>[[ELO]]</b>. In deinen ersten <b>[[NEWGAMES]]</b> Spielen kann dich ein einziges Spiel um bis zu <b>[[KNEW]]</b> Punkte bewegen, damit du schnell dein Niveau findest; danach um bis zu <b>[[KEST]]</b>.</p>'
  '<p>Wie viel du dich bewegst, hängt davon ab, wen du schlägst. Eine stärkere Seite zu schlagen bringt fast das Maximum; eine viel schwächere bringt fast nichts. Verlieren funktioniert genauso, nur umgekehrt.</p>'
  '<p>Die Stärke eines Teams ist der Durchschnitt aller Mitglieder, also bringt es nichts, schwache Teams abzufarmen &mdash; aufsteigen heißt, Leute zu schlagen, die selbst hoch gewertet sind. Auch wer neben dir spielt, zählt: Deine Veränderung mischt deine eigene Wertung mit dem Durchschnitt deines Teams, also bringt es mehr, schwache Mitspieler zum Sieg zu tragen, als derselbe Sieg in einem starken Team &mdash; und eine Niederlage mit schwachen Mitspielern kostet weniger.</p>'),

 ('Ganz und halb',
  '<p>Weil der Beobachter jedes Spiel von Anfang an verfolgt, sieht er genau, wann dein Schiff zu der Seite kam, die am Ende gewann. In der ersten Hälfte des Spiels dazugekommen, zählt der Sieg <b>voll</b>. In der zweiten Hälfte zählt er <b>höchstens zur Hälfte</b> &mdash; weniger, je weniger vom Spiel du dabei warst.</p>'
  '<p>Eine Niederlage zählt immer voll: Spät zu kommen ist kein Weg, weniger zu verlieren. Entscheidend ist, wann du wirklich beigetreten bist, nicht wann du auf Spielen gedrückt hast.</p>'),

 ('Regeln, die man kennen sollte',
  '<p><b>Punkte zählen, nicht nur Anwesenheit.</b> Um gewertet zu werden, musst du im Spiel irgendwann <b>[[MINPEAK]]</b> erreicht haben, wenn deine Seite gewonnen hat, oder <b>[[MINLOSE]]</b>, wenn sie verloren hat. In einer Lobby zu sitzen ist kein Spielen.</p>'
  '<p><b>Früh gehen verhindert keine Niederlage.</b> Jeder, der für die verlierende Seite gespielt hat, bekommt sie angerechnet, ob er am Ende noch da war oder nicht.</p>'
  '<p><b>Wer eine scheinbar geschlagene Seite verlässt, bekommt ihr Comeback nicht.</b> Hatte deine Seite unter 25 % Siegchance, als du gegangen bist, und warst du noch weg, als sie mehr als zehn Minuten später gewann, gehört der Sieg nicht dir. Deine Kontoseite sagt es dir.</p>'),

 ("Zwei Namen",
  '<p><b>Dein Kontoname</b> ist die Zeile in der Rangliste, die dir gehört. Dort lebt deine'
  ' Wertung, und sie ändert sich nicht, wenn du dich im Spiel umbenennst. Einzustellen in'
  ' den <a href="/settings">Einstellungen</a>.</p><p><b>Dein Spielname</b> ist das, wie du'
  ' in Starblast gerade heißt. Einzustellen auf der Seite <a href="/play">Spielen</a>, und'
  ' so oft zu ändern, wie du magst &mdash; daran erkennen wir dein Schiff in einer Lobby,'
  ' und ein Spiel unter diesem Namen zählt für dein Konto.</p><p>Am Anfang sind beide'
  ' gleich, und bei den meisten bleiben sie es. Sie unterscheiden sich nur, wenn du eine'
  ' Weile unter etwas anderem spielst.</p>'),

 ("Anmelden vor dem Spiel, und der grüne Haken",
  '<p><b>Spielen</b> zu drücken, bevor ein Spiel losgeht, verbindet die beiden Namen. Die'
  ' Seite hält in dieser Lobby nach einem Schiff mit deinem <b>Spielnamen</b> Ausschau,'
  ' entscheidet, dass dieses Schiff du bist, und schreibt das Ergebnis deinem'
  ' <b>Kontonamen</b> gut &mdash; so wächst deine Wertung an einer Stelle, egal wie du im'
  ' Spiel heißt.</p><p>Halte also den Spielnamen auf der Seite Spielen gleich dem Namen'
  ' deines Schiffs. Der muss übereinstimmen; dein Kontoname nicht.</p><p><b>Meldest du dich'
  ' nicht an</b>, zählt ein Spiel unter deinem Spielnamen trotzdem für dich. Was die'
  ' Anmeldung hinzufügt, ist der Beleg, welches Schiff deins war: Fliegt in derselben Lobby'
  ' jemand anderes unter deinem Namen, wird das Spiel zurückgehalten, falls du dich nicht'
  ' angemeldet hast, und der <b>Schutz</b> zählt nur die Spiele, für die du dich angemeldet'
  ' hast. Ein Spielname, den zwei Konten beanspruchen, zählt für keines.</p><p>Ein'
  ' <b>&#10003;</b> neben einem Namen heißt, dass dieser Spieler den Schutz eingeschaltet'
  ' hat: Für ihn zählen nur Spiele, für die er sich angemeldet hat. Das ist eine strengere,'
  ' langsamere Wertung, und sie ist freiwillig &mdash; zu finden in den <a'
  ' href="/settings">Einstellungen</a>.</p>'),

 ("Clans",
  '<p>Ein Clan ist eine Gruppe von Spielern, die sich ein Kürzel teilen. Seine Seite zeigt'
  ' die nach Stärke sortierte Mannschaft, die gemeinsame Bilanz, seine Survival-Siege und wo'
  ' der Clan spielt.</p><p><b>Beitreten.</b> <a href="/social">Social</a> schlägt dir die'
  ' Clans vor, deren Mitglieder ungefähr auf deinem Niveau spielen, und zeigt dir jeden'
  ' Clan, der Anfragen annimmt. Du kannst auch die Seite eines Clans öffnen und <b>Beitritt'
  ' anfragen</b> drücken, oder einen Einladungslink nutzen, den dir sein Anführer gibt. So'
  ' oder so entscheidet der Anführer. Trägt dein Spielname das Kürzel des Clans schon, wenn'
  ' der Clan angelegt wird, wirst du automatisch aufgenommen.</p><p><b>Dein Kürzel wird'
  ' genau so angezeigt, wie es geschrieben ist</b> &mdash; samt Zierbuchstaben. Die Fassung'
  ' in einfachen Buchstaben wird nur hinter den Kulissen benutzt, damit jede Schreibweise'
  ' eines Kürzels als ein Clan zählt und die Suche in beide Richtungen funktioniert. Ein'
  ' Anführer kann unter <a href="/myclan">Dein Clan</a> weitere Schreibweisen des Kürzels'
  ' anlegen, und jedes Mitglied wählt unter <a href="/account">Dein Konto</a> die, die es'
  ' tragen will.</p><p><b>Ein Spiel unter dem Kürzel deines Clans zählt für dich</b>, in'
  ' welcher Schreibweise das Kürzel auch getippt ist. Nur Mitglieder dieses Clans werden so'
  ' zugeordnet, und was auf das Kürzel folgt, muss dein Name sein.</p><p><b>Dein Kontoname'
  ' bist nur du.</b> Trittst du einem Clan bei, kommt das Kürzel aus deinem Kontonamen'
  ' heraus und erscheint stattdessen als Abzeichen daneben &mdash; so kann sich das Kürzel'
  ' ändern, und auch dein Clan, ohne dass deine Bilanz umzieht. Die Kontoseite fragt nach,'
  ' bevor sie einen Namen mit Kürzel speichert.</p><p><b>Ränge.</b> Ein Anführer kann'
  ' Co-Anführer und Moderatoren ernennen. Ein Moderator entfernt normale Mitglieder; ein'
  ' Co-Anführer kann alles, was der Anführer kann, außer den Clan zu löschen oder einen'
  ' anderen Co-Anführer anzufassen. Niemand kann jemanden des eigenen Rangs oder darüber'
  ' entfernen.</p>'),

 ('Ein Name, der schon in der Rangliste steht',
  '<p>Gib ihn in den <a href="/settings">Einstellungen</a> ein, und wenn er niemandem gehört, ist er sofort deiner. Hat er schon eine Bilanz, bietet dir die Seite stattdessen an, ihn zu <b>beanspruchen</b>. Beweise, dass er dir gehört, indem du ein gewertetes Deathmatch-Spiel spielst &mdash; der Befehl <b>/proveclaim</b> des Discord-Bots führt dich durch &mdash; oder warte, bis [[CONTACT]] ihn prüft. Solange ein Anspruch offen ist, steht er auf der Seite dieses Spielers, damit der echte Besitzer ihn melden kann.</p>'
  '<p>Dasselbe passiert, wenn ein Name in der Rangliste genauso <b>gelesen</b> wird wie der, den du eingegeben hast &mdash; ein normaler Name gegen eine Version mit verzierten Buchstaben. Dort landen deine Spiele, also wird dir diese Zeile angeboten. Ist es wirklich jemand anderes, speichere deinen Namen trotzdem.</p>'),

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

 ('Häufige Fragen',
  '<div class="qa"><b>Ich habe gewonnen, aber nichts ist passiert.</b> Ergebnisse kommen etwa zehn Minuten nach dem Ende eines Spiels an. Dauert es länger, ist es meist eines davon: Das Spiel lief weniger als zehn Minuten, du warst nicht die nötigen zehn Minuten dabei, deine Punktzahl hat das Minimum nicht erreicht, oder du hast deine Seite verlassen, als sie verlor, und warst noch weg, als sie gewann.<b>Mein Name steht zweimal in der Rangliste.</b> Eine andere Schreibweise zählt als anderer Spieler, weil das Spiel nur das meldet. Beanspruche den, unter dem du wirklich spielst.<b>Die Rangliste wurde zurückgesetzt.</b> Die Wertungen werden noch getestet und können wieder gelöscht werden. Nichts, was du tust, ist umsonst; die Rangliste fängt nur von vorn an.<b>Etwas stimmt nicht.</b> Sag es unter <a href="/reports">Melden</a> oder gib [[CONTACT]] auf Discord Bescheid. Ein Mensch liest es.</div>'),
 ("Divisionen",
  '<p>Deine Division ist dein Platz unter allen gewerteten Spielern der Gesamtrangliste, keine Wertungszahl — sie ändert sich also, wenn sich die Spieler um dich herum bewegen. Spieler in ihren ersten Partien zählen nicht mit.</p>'
  '[[RANKS]]'),
]
