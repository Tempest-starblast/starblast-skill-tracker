# -*- coding: utf-8 -*-
"""The Info page in English. The other languages follow this one - if you
change the wording here, the translations are now out of date."""

TITLE = "Info"
SUB = "How this site works, in short."
SEARCH = "Search this page\u2026"
NOMATCH = "Nothing on this page matches that."
FOOT = 'Questions? Ask [[CONTACT]] on Discord.'

CARDS = [
 ("What this is",
  '<p class="lead">A skill ranking for Starblast team mode. Play team games, win, and your'
  ' rating goes up. Nothing to install and nothing to sign up for &mdash; you are on the'
  ' board as soon as you win a match we are watching.</p>'),

 ("Getting started",
  '<ol>'
  '<li>Open the <a href="/play">Play</a> tab and pick a match marked as tracked.</li>'
  '<li>Press <b>Play</b>. Your name is copied, ready to paste into Starblast.</li>'
  '<li>Play the game. When it ends, the result appears here within a minute.</li>'
  '</ol>'
  '<p>That is all that is required. Signing in is optional and only needed for the extras'
  ' below.</p>'),

 ("Which games count",
  '<p>Every live team match is watched, from the moment the lobby appears. There is no limit'
  ' on how many at once and no minimum number of players for a lobby to be picked up.</p>'
  '<p>To be <b>rated</b>, a match has to run <b>at least ten minutes</b>. Shorter games are'
  ' still recorded and can be watched back, but they move nobody&rsquo;s rating.</p>'
  '<p>Inside a rated match, each team&rsquo;s <b>top eight by score</b> are the players rated,'
  ' and you need roughly <b>ten minutes in the match</b> to be one of them &mdash; a winner'
  ' needs that however early they arrived.</p>'
  '<p>The <a href="/play">Play</a> tab lists every live match and whether the watcher is on'
  ' it yet; a brand-new lobby is picked up within a few seconds. If a match is live, it'
  ' counts.</p>'),

 ("Your rating",
  '<p>Everyone starts at <b>[[ELO]]</b>. A match moves you by at most <b>[[K]]</b>'
  ' points.</p>'
  '<p>How much you move depends on who you beat. Beating a stronger side gains close to the'
  ' full amount; beating a much weaker one gains almost nothing. Losing works the same in'
  ' reverse. Two even teams move by exactly one point.</p>'
  '<p>A team&#39;s strength is the average of everyone on it, so farming weak teams'
  ' will not lift you &mdash; climbing means beating people who are rated highly'
  ' themselves. Who stands beside you counts too: your swing blends your own rating with your team&#39;s average, so carrying weak allies to a win pays more than the same win inside a stacked team &mdash; and losing beside weak allies costs less.</p>'),

 ("Full and half",
  '<p>Because the watcher follows every match from its start, it sees exactly when your ship'
  ' joined. Play from early on and you count in <b>full</b>; walk into a game already well'
  ' underway and it counts at <b>half</b> &mdash; for winners and losers alike. It is judged'
  ' on when you actually joined the match, not on when you press Play.</p>'),

 ("Two rules worth knowing",
  '<p><b>Leaving early does not dodge a loss.</b> A losing team is charged as its fullest'
  ' roster, not as whoever was still there at the end.</p>'
  '<p><b>A score under [[MINSCORE]] is not rated at all</b>, win or lose. Sitting in a lobby is'
  ' not playing.</p>'),

 ("Two names",
  '<p><b>Your account name</b> is the row on the leaderboard that belongs to you. That is'
  ' where your rating lives, and it does not change when you rename in game. Set it in'
  ' <a href="/settings">Settings</a>.</p>'
  '<p><b>Your play name</b> is whatever you are called in Starblast right now. Set it on'
  ' the <a href="/play">Play</a> page, and change it as often as you like &mdash; it is how'
  ' we recognise your ship in a lobby, nothing more.</p>'
  '<p>They start out the same, and for most people they stay the same. They only differ if'
  ' you play under something else for a while.</p>'),

 ("Checking in, and the green tick",
  '<p>Pressing <b>Play</b> before a match is what ties the two names together. The site'
  ' watches that lobby for a ship called by your <b>play name</b>, decides that ship is'
  ' you, and puts the result on your <b>account name</b> &mdash; so your rating grows in'
  ' one place however you are called in game.</p>'
  '<p>So keep the play name on the Play page the same as the name in your ship. That is the'
  ' one that has to match; your account name does not.</p>'
  '<p><b>If you do not check in</b>, the result simply lands on whatever name the game'
  ' reported. That only counts for you if you own that name.</p>'
  '<p>A <b>&#10003;</b> beside a name means that player has Protection switched on: only'
  ' matches they checked into count for them. It is a stricter, slower rating, and it is'
  ' optional &mdash; find it in <a href="/settings">Settings</a>.</p>'),

 ("Clans",
  '<p>A clan is a group of players who share a tag. Its page shows the roster ranked by'
  ' skill, the combined record, and where the clan plays.</p>'
  '<p><b>Joining one.</b> <a href="/social">Social</a> suggests the clans whose members'
  ' play at about your standard, and will show you every clan that takes applications.'
  ' You can also open a clan&#39;s page and press <b>Apply to join</b>, or use'
  ' an invite link its leader gives you. Either way the leader decides. If your in-game'
  ' name already carries the clan&#39;s tag when the clan is created, you are added'
  ' automatically.</p>'
  '<p><b>Your tag is shown exactly as it is written</b> &mdash; fancy letters and all. The'
  ' plain-letter version is only used behind the scenes, so that every styling of a tag'
  ' counts as one clan and searching for it works either way.</p>'
  '<p><b>Ranks.</b> A leader can appoint co-leaders and moderators. A moderator removes'
  ' ordinary members; a co-leader does everything the leader can except delete the clan or'
  ' touch another co-leader. Nobody can remove someone of their own rank or above.</p>'),

 ("A name that is already on the board",
  '<p>Type it in <a href="/settings">Settings</a> and, if nobody owns it, it is yours at'
  ' once. If it already has a record the page offers to <b>claim</b> it instead: it becomes'
  ' yours the next time that name wins a tracked match, which is how we know it is really'
  ' you rather than someone helping themselves to your rating.</p>'
  '<p>The same happens if a name already on the board <b>reads</b> the same as the one you'
  ' typed &mdash; a plain name against a fancy-lettered version of it. That row is where'
  ' your matches are landing, so it offers you that one instead. If it is genuinely someone'
  ' else, save your name anyway.</p>'),

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

 ("Common questions",
  '<div class="qa">'
  '<b>I won but nothing happened.</b>'
  ' Every live match is watched now, so it is usually one of three things: the match ran'
  ' under ten minutes, you were not in your team&rsquo;s top eight by score, or you were not'
  ' in it for the ten minutes a rating needs.'
  '<b>My name is on the board twice.</b>'
  ' A different spelling counts as a different player, because that is all the game reports.'
  ' Claim the one you actually play under.'
  '<b>The board reset.</b>'
  ' Ratings are still being tested and may be wiped again. Nothing you do is wasted; the'
  ' board just starts over.'
  '<b>Something looks wrong.</b>'
  ' Say so on <a href="/reports">Report</a> or tell [[CONTACT]] on Discord. It is read by a'
  ' person.'
  '</div>'),
 ("Ranks",
  '<p>Your division is your place among every ranked player on the all-time'
  ' board, not a rating number &mdash; so it moves as the players around you'
  ' move. Players still in their first few matches are not counted.</p>'
  '[[RANKS]]'),
 ("Replays",
  '<p>Every watched match is recorded, and any of them can be played back from the'
  ' <a href="/replays">Replays</a> page &mdash; the radar with each ship drawn as the hull it'
  ' was actually flying, the stations module by module, the win chance, and the scoreboard'
  ' moving the way it moved. Hover a pilot to find their ship on the map, or a ship to find'
  ' their row.</p>'
  '<p>A replay opens at the start of the match, not at the point the watcher began rating'
  ' it.</p>'),

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
  ' ten, which is also to say it is wrong the other three.</p>'),

 ("Ranks on Discord",
  '<p>In the Discord server the bot gives you a coloured role for your division and keeps it'
  ' in step as you move. The roles are hoisted, so the member list reads from Shadow X-3 at'
  ' the top down to Fly, and reaching a new one is announced in the server.</p>'
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
