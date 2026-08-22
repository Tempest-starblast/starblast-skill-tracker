# -*- coding: utf-8 -*-
"""The Info page in English. The other languages follow this one - if you
change the wording here, the translations are now out of date."""

TITLE = "Info"
SUB = "How this site works, in short."
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
  '<p>We can only watch a few matches at a time, so not every game counts. A match is'
  ' watchable once it is <b>20 minutes old</b>, until it is 90 minutes old, and it needs'
  ' at least four players.</p>'
  '<p>The <a href="/play">Play</a> tab shows exactly which lobbies are being watched right'
  ' now. If a game is not on that list, nothing from it is recorded &mdash; it does not'
  ' arrive later.</p>'),

 ("Your rating",
  '<p>Everyone starts at <b>[[ELO]]</b>. A match moves you by at most <b>[[K]]</b>'
  ' points.</p>'
  '<p>How much you move depends on who you beat. Beating a stronger side gains close to the'
  ' full amount; beating a much weaker one gains almost nothing. Losing works the same in'
  ' reverse. Two even teams move by exactly one point.</p>'
  '<p>A team&#39;s strength is the average of everyone on it, so farming weak teams'
  ' will not lift you &mdash; climbing means beating people who are rated highly'
  ' themselves.</p>'),

 ("Full and half",
  '<p>If you were already in the match when we started watching, it counts in full. Join a'
  ' match that is already being watched and it still counts, at <b>half</b> &mdash; for'
  ' winners and losers alike. The Play tab says which is which before you join.</p>'),

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
  '<p><b>Joining one.</b> Open the clan&#39;s page and press <b>Apply to join</b>, or use'
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
  ' The match was probably not one of the watched ones. The Play tab lists them before you'
  ' join.'
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
]
