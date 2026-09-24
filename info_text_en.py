# -*- coding: utf-8 -*-
"""The Info page in English. The other languages follow this one - if you
change the wording here, the translations are now out of date."""

TITLE = "Info"
SUB = "How this site works, in short."
SEARCH = "Search this page\u2026"
NOMATCH = "Nothing on this page matches that."
FOOT = 'Questions? Ask [[CONTACT]] on Discord.'

CARDS = [
 ('What this is',
  '<p class="lead">A skill ranking for Starblast team mode. Play team games, win, and your rating goes up. Nothing to install and nothing to sign up for &mdash; you are on the board as soon as you play a match we rate.</p>'),

 ('Getting started',
  '<ol><li>Open the <a href="/play">Play</a> tab and pick a match.</li>'
  '<li>Press <b>Play</b>. Your name is copied, ready to paste into Starblast.</li>'
  '<li>Play the game. When it ends, the result appears here within about ten minutes.</li>'
  '</ol>'
  '<p>That is all it takes. Signing in is optional and only needed for the extras below.</p>'),

 ("Which games count",
  '<p>Every live team match is watched, from the moment the lobby appears. There is no limit'
  ' on how many at once and no minimum number of players for a lobby to be picked up.</p>'
  '<p>To be <b>rated</b>, a match has to run <b>at least ten minutes</b>. Shorter games are'
  ' still recorded and can be watched back, but they move nobody&rsquo;s rating.</p>'
  '<p>Inside a rated match, <b>everyone</b> who was in it for <b>ten minutes</b> and reached'
  ' the minimum score is rated, win or lose. Only time the watcher saw counts.</p>'
  '<p>The <a href="/play">Play</a> tab lists every live match and whether the watcher is on'
  ' it yet; a brand-new lobby is picked up within a few seconds. If a match is live, it'
  ' counts.</p>'
  '<p>The time you spend in rated matches is added up on your profile &mdash; all-time, with the last fortnight beside it. The watcher measures it, so it follows the same rules as everything above: an unrated match, or a lobby nobody was watching, counts nothing. The clock started on 21 September 2026.</p>'),

 ('Your rating',
  '<p>Everyone starts at <b>[[ELO]]</b>. In your first <b>[[NEWGAMES]]</b> matches one match can move you by up to <b>[[KNEW]]</b> points, so you find your level quickly; after that, by up to <b>[[KEST]]</b>.</p>'
  '<p>How much you move depends on who you beat. Beating a stronger side gains close to the full amount; beating a much weaker one gains almost nothing. Losing works the same in reverse.</p>'
  '<p>A team&#39;s strength is the average of everyone on it, so farming weak teams will not lift you &mdash; climbing means beating people who are rated highly themselves. Who stands beside you counts too: your swing blends your own rating with your team&#39;s average, so carrying weak allies to a win pays more than the same win inside a stacked team &mdash; and losing beside weak allies costs less.</p>'),

 ('Full and half',
  '<p>Because the watcher follows every match from its start, it sees exactly when your ship joined the side that went on to win. Join it in the first half of the match and the win counts in <b>full</b>. Join it in the second half and it counts for <b>at most half</b> &mdash; less, the less of the match you were there for.</p>'
  '<p>A loss always counts in full: arriving late is not a way to lose less. It is judged on when you actually joined, not on when you pressed Play.</p>'),

 ('Rules worth knowing',
  '<p><b>You need a score, not just a seat.</b> To be rated you must have reached <b>[[MINPEAK]]</b> at some point in the match if your side won, or <b>[[MINLOSE]]</b> if it lost. Sitting in a lobby is not playing.</p>'
  '<p><b>Leaving early does not dodge a loss.</b> Everyone who played for the losing side is charged, whether or not they were still there at the end.</p>'
  '<p><b>Walking out on a side that looks beaten does not earn you its comeback.</b> If your side had under a 25% chance of winning when you left, and you were still gone when it won, more than ten minutes later, the win is not yours. Your account page says so.</p>'),

 ("Two names",
  '<p><b>Your account name</b> is the row on the leaderboard that belongs to you. That is'
  ' where your rating lives, and it does not change when you rename in game. Set it in'
  ' <a href="/settings">Settings</a>.</p>'
  '<p><b>Your play name</b> is whatever you are called in Starblast right now. Set it on'
  ' the <a href="/play">Play</a> page, and change it as often as you like &mdash; it is how'
  ' we recognise your ship in a lobby, and a match played under it counts for your'
  ' account.</p>'
  '<p>They start out the same, and for most people they stay the same. They only differ if'
  ' you play under something else for a while.</p>'),

 ("Checking in, and the green tick",
  '<p>Pressing <b>Play</b> before a match is what ties the two names together. The site'
  ' watches that lobby for a ship called by your <b>play name</b>, decides that ship is'
  ' you, and puts the result on your <b>account name</b> &mdash; so your rating grows in'
  ' one place however you are called in game.</p>'
  '<p>So keep the play name on the Play page the same as the name in your ship. That is the'
  ' one that has to match; your account name does not.</p>'
  '<p><b>If you do not check in</b>, a match under your play name still counts for you.'
  ' What the check-in adds is proof of which ship was yours: if somebody else flies your'
  ' name in the same lobby, the match is held unless you checked in, and'
  ' <b>Protection</b> counts only the matches you checked into. A play name two accounts'
  ' both claim counts for neither.</p>'
  '<p>A <b>&#10003;</b> beside a name means that player has Protection switched on: only'
  ' matches they checked into count for them. It is a stricter, slower rating, and it is'
  ' optional &mdash; find it in <a href="/settings">Settings</a>.</p>'),

 ("Clans",
  '<p>A clan is a group of players who share a tag. Its page shows the roster ranked by'
  ' skill, the combined record, its survival wins, and where the clan plays.</p>'
  '<p><b>Joining one.</b> <a href="/social">Social</a> suggests the clans whose members'
  ' play at about your standard, and will show you every clan that takes applications.'
  ' You can also open a clan&#39;s page and press <b>Apply to join</b>, or use'
  ' an invite link its leader gives you. Either way the leader decides. If your in-game'
  ' name already carries the clan&#39;s tag when the clan is created, you are added'
  ' automatically.</p>'
  '<p><b>Your tag is shown exactly as it is written</b> &mdash; fancy letters and all. The'
  ' plain-letter version is only used behind the scenes, so that every styling of a tag'
  ' counts as one clan and searching for it works either way. A leader can add other'
  ' stylings of the tag on <a href="/myclan">Your clan</a>, and each member picks the one'
  ' to wear on <a href="/account">Your account</a>.</p>'
  '<p><b>A match under your clan&#39;s tag counts for you</b>, whatever styling the tag is'
  ' typed in. Only members of that clan are matched this way, and what follows the tag has'
  ' to be your name.</p>'
  '<p><b>Your account name is just you.</b> When you join a clan the tag comes off your'
  ' account name and shows beside it as the badge instead, so the tag can change, and so can'
  ' your clan, without your record moving. The account page asks before saving a name that'
  ' carries a tag.</p>'
  '<p><b>Ranks.</b> A leader can appoint co-leaders and moderators. A moderator removes'
  ' ordinary members; a co-leader does everything the leader can except delete the clan or'
  ' touch another co-leader. Nobody can remove someone of their own rank or above.</p>'),

 ('A name that is already on the board',
  '<p>Type it in <a href="/settings">Settings</a> and, if nobody owns it, it is yours at once. If it already has a record the page offers to <b>claim</b> it instead. Prove it is yours by playing one ranked Deathmatch game &mdash; the Discord bot&#39;s <b>/proveclaim</b> walks you through it &mdash; or wait for [[CONTACT]] to review it. While a claim is open it shows on that player&#39;s page, so the real owner can report it.</p>'
  '<p>The same happens if a name already on the board <b>reads</b> the same as the one you typed &mdash; a plain name against a fancy-lettered version of it. That row is where your matches are landing, so it offers you that one instead. If it is genuinely someone else, save your name anyway.</p>'),

 ("Running a clan",
  '<p>Clans are handed out by hand. Ask on the <a href="/clans">Clans</a> page and'
  ' [[CONTACT]] approves or turns it down on Discord. If you are turned down you may ask'
  ' again.</p>'
  '<p>Once approved you claim your tag, and a <b>Your clan</b> tab appears with everything'
  ' in one place: the invite link, who is waiting to join, the roster, ranks, the region,'
  ' and deleting the clan.</p>'),

 ("Languages",
  '<p>Pick a language in the header of any page &mdash; English, Espa&ntilde;ol,'
  ' Fran&ccedil;ais, Deutsch, Italiano, Русский, Tiếng Việt, 中文 or فارسی. The whole site is'
  ' translated, this page included. The English is the original, so if a translation ever'
  ' reads oddly, that is where the meaning lives.</p>'),

 ("Discord",
  '<p>The bot does nearly everything this site does &mdash; leaderboards, your profile,'
  ' clans, applying, and setting ranks. Ask [[CONTACT]] for an invite, then use <b>/help</b>'
  ' to see the commands.</p>'),

 ("What we know about you",
  '<p><b>No IP addresses are stored.</b> Not when you visit, not when you press Play, not'
  ' when you sign in.</p>'
  '<p>Signing in with Discord gives us your account id and handle. Google gives an account'
  ' id. That is all &mdash; no email, and nothing that could be used to contact you.</p>'
  '<p>The site&#39;s code is public, so any of this can be checked rather than taken on'
  ' trust.</p>'),

 ('Common questions',
  '<div class="qa"><b>I won but nothing happened.</b> Results take about ten minutes to arrive after a match ends. After that it is usually one of these: the match ran under ten minutes, you were not in it for the ten minutes a rating needs, your score never reached the minimum, or you left your side while it was losing and were still gone when it won.<b>My name is on the board twice.</b> A different spelling counts as a different player, because that is all the game reports. Claim the one you actually play under.<b>The board reset.</b> Ratings are still being tested and may be wiped again. Nothing you do is wasted; the board just starts over.<b>Something looks wrong.</b> Say so on <a href="/reports">Report</a> or tell [[CONTACT]] on Discord. It is read by a person.</div>'),
 ("Ranks",
  '<p>Your division is your place among every ranked player on the all-time'
  ' board, not a rating number &mdash; so it moves as the players around you'
  ' move. Players still in their first few matches are not counted.</p>'
  '[[RANKS]]'),
 ('Replays',
  '<p>Every watched match is recorded, and can be played back from the <a href="/replays">Replays</a> page for <b>[[REPLAYDAYS]] days</b> &mdash; the radar with each ship drawn as the hull it was actually flying, the stations module by module, the win chance, and the scoreboard moving the way it moved. Hover a pilot to find their ship on the map, or a ship to find their row.</p>'
  '<p>After that the result and who played are kept, but not the playback. <b>Save</b> a replay and it is yours to keep and open again later.</p>'
  '<p>A replay opens at the start of the match, not at the point the watcher began rating it.</p>'),

 ("Live matches",
  '<p>The <a href="/live">Live</a> tab is that same screen in real time: three team panels'
  ' around the radar, each with its station, its gems and its win chance. Back and Next move'
  ' between the lobbies being watched.</p>'
  '<p>It runs about two minutes behind and without player names, so nothing on it can be used'
  ' to find someone in a game that is still going.</p>'),

 ("The win chance",
  '<p>The percentage beside each team is a model&rsquo;s estimate of how often a side in that'
  ' position goes on to win. It learns from finished matches &mdash; the scores, which way'
  ' they are moving, the stations, and how strong the players on each side are &mdash; and it'
  ' is retrained every night on the matches played since.</p>'
  '<p>It is a forecast, not a verdict. When it says 70%, that side wins about seven times in'
  ' ten and loses the other three.</p>'),

 ("Ranks on Discord",
  '<p>In the Discord server the bot gives you a coloured role for your division and keeps it'
  ' in step as you move. The roles are hoisted, so the member list reads from Mythos at the'
  ' top down to Drifter, and reaching a new one is announced in the server.</p>'
  '<p>Ask [[CONTACT]] for an invite.</p>'),
 ("Friends and clanmates",
  '<p>Send a friend request from anyone&rsquo;s profile, or by name on the'
  ' <a href="/social">Social</a> page. Once you both agree, each of you can see which lobby'
  ' the other is in while they are playing, and join them with one press.</p>'
  '<p>Only people you accepted can see that, and all they see is the lobby and its region'
  ' &mdash; not your score, not where you are on the map. The public live view stays about two'
  ' minutes behind and without names, exactly as it was.</p>'
  '<p>Clanmates appear the same way without being added, since you already share a tag in'
  ' public. Beside each name is whether they <b>checked in</b>: a player who has not is having'
  ' the result recorded against whatever name the game reports rather than against their'
  ' account, and they can still fix that from <a href="/play">Play</a> before the match'
  ' ends.</p>'
  '<p>Pressing <b>Join</b> checks you in for that lobby and opens it, so joining a friend'
  ' counts exactly as pressing Play does.</p>'),
]
