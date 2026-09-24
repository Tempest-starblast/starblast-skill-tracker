# -*- coding: utf-8 -*-
"""La page Infos en français. L'original est info_text_en.py."""

TITLE = "Infos"
SUB = "Comment ce site fonctionne, en bref."
SEARCH = "Rechercher sur cette page…"
NOMATCH = "Rien sur cette page ne correspond."
STALE = ()
FOOT = 'Des questions ? Demandez à [[CONTACT]] sur Discord.'

CARDS = [
 ("Ce que c'est",
  '<p class="lead">Un classement de niveau pour le mode équipe de Starblast. Jouez des parties en équipe, gagnez, et votre note monte. Rien à installer ni à créer &mdash; vous êtes au classement dès que vous jouez une partie que nous notons.</p>'),

 ('Pour commencer',
  '<ol><li>Ouvrez l’onglet <a href="/play">Jouer</a> et choisissez une partie.</li>'
  '<li>Appuyez sur <b>Jouer</b>. Votre nom est copié, prêt à coller dans Starblast.</li>'
  '<li>Jouez. Quand la partie se termine, le résultat apparaît ici en une dizaine de minutes.</li>'
  '</ol>'
  '<p>C’est tout. Se connecter est facultatif et ne sert que pour les options ci-dessous.</p>'),

 ('Quelles parties comptent',
  '<p>Chaque partie en équipe en direct est suivie, dès que la salle apparaît. Il n’y a pas de limite au nombre de parties à la fois ni de minimum de joueurs pour qu’une salle soit prise en compte.</p>'
  '<p>Pour être <b>notée</b>, une partie doit durer <b>au moins dix minutes</b>. Les plus courtes sont quand même enregistrées et peuvent être revues, mais elles ne changent la note de personne.</p>'
  '<p>Dans une partie notée, <b>tous ceux</b> qui y ont passé <b>dix minutes</b> et atteint le score minimum sont notés, victoire ou défaite. Seul compte le temps que l’observateur a vu.</p>'
  '<p>L’onglet <a href="/play">Jouer</a> liste chaque partie en direct et indique si l’observateur y est déjà ; une nouvelle salle est prise en compte en quelques secondes. Si une partie est en direct, elle compte.</p>'
  '<p>Le temps passé en parties notées s’additionne sur votre profil &mdash; au total, avec les deux dernières semaines à côté. C’est l’observateur qui le mesure, donc il suit les mêmes règles que tout le reste : une partie non notée, ou une salle que personne ne suivait, ne compte pas. Le compteur a démarré le 21 septembre 2026.</p>'),

 ('Votre niveau',
  '<p>Tout le monde commence à <b>[[ELO]]</b>. Pendant vos <b>[[NEWGAMES]]</b> premières parties, une seule partie peut vous faire bouger de <b>[[KNEW]]</b> points au plus, pour trouver vite votre niveau ; ensuite, de <b>[[KEST]]</b> au plus.</p>'
  '<p>Ce que vous gagnez dépend de qui vous battez. Battre un camp plus fort rapporte presque le maximum ; battre un camp bien plus faible ne rapporte presque rien. Perdre fonctionne de la même façon, à l’envers.</p>'
  '<p>La force d’une équipe est la moyenne de tous ses membres, donc battre des équipes faibles ne vous fera pas monter &mdash; monter, c’est battre des joueurs eux-mêmes bien notés. Vos coéquipiers comptent aussi : votre variation mélange votre propre note avec la moyenne de votre équipe, donc porter des alliés faibles jusqu’à la victoire rapporte plus que la même victoire dans une équipe très forte &mdash; et perdre aux côtés d’alliés faibles coûte moins.</p>'),

 ('Pleine et demie',
  '<p>Comme l’observateur suit chaque partie depuis le début, il voit exactement quand votre vaisseau a rejoint le camp qui a fini par gagner. Rejoint dans la première moitié de la partie, la victoire compte <b>en entier</b>. Dans la seconde moitié, elle compte <b>au plus à moitié</b> &mdash; moins encore si vous avez été là peu de temps.</p>'
  '<p>Une défaite compte toujours en entier : arriver tard n’est pas une façon de perdre moins. On juge sur le moment où vous êtes vraiment entré, pas sur celui où vous avez appuyé sur Jouer.</p>'),

 ('Règles à connaître',
  '<p><b>Il faut marquer, pas seulement être là.</b> Pour être noté, vous devez avoir atteint <b>[[MINPEAK]]</b> à un moment de la partie si votre camp a gagné, ou <b>[[MINLOSE]]</b> s’il a perdu. Rester dans une salle, ce n’est pas jouer.</p>'
  '<p><b>Partir tôt n’évite pas une défaite.</b> Tous ceux qui ont joué pour le camp perdant la subissent, qu’ils soient encore là à la fin ou non.</p>'
  '<p><b>Quitter un camp qui semble battu ne vous donne pas sa remontée.</b> Si votre camp avait moins de 25 % de chances quand vous êtes parti, et que vous étiez encore absent quand il a gagné, plus de dix minutes après, la victoire n’est pas la vôtre. Votre page de compte l’indique.</p>'),

 ("Deux noms",
  '<p><b>Votre nom de compte</b> est la ligne du classement qui vous appartient. C&#39;est'
  ' là que vit votre niveau, et il ne change pas quand vous vous renommez en jeu. Il se'
  ' règle dans <a href="/settings">Paramètres</a>.</p><p><b>Votre nom de jeu</b> est celui'
  ' que vous portez dans Starblast en ce moment. Il se règle sur la page <a'
  ' href="/play">Jouer</a>, et vous pouvez le changer autant que vous voulez &mdash;'
  ' c&#39;est à lui que nous reconnaissons votre vaisseau dans un salon, et une partie jouée'
  ' sous ce nom compte pour votre compte.</p><p>Au départ ce sont les mêmes, et pour la'
  ' plupart des gens ils le restent. Ils ne diffèrent que si vous jouez sous un autre nom'
  ' pendant un temps.</p>'),

 ("L'annonce avant la partie, et la coche verte",
  '<p>Appuyer sur <b>Jouer</b> avant une partie, c&#39;est ce qui relie les deux noms. Le'
  ' site guette dans ce salon un vaisseau portant votre <b>nom de jeu</b>, décide que ce'
  ' vaisseau c&#39;est vous, et met le résultat sur votre <b>nom de compte</b> &mdash; ainsi'
  ' votre niveau grandit au même endroit, quel que soit votre nom en jeu.</p><p>Gardez donc'
  ' le nom de jeu de la page Jouer identique à celui de votre vaisseau. C&#39;est celui-là'
  ' qui doit correspondre ; pas votre nom de compte.</p><p><b>Si vous ne vous annoncez'
  ' pas</b>, une partie sous votre nom de jeu compte quand même pour vous. Ce que'
  ' l&#39;annonce ajoute, c&#39;est la preuve de quel vaisseau était le vôtre : si'
  ' quelqu&#39;un d&#39;autre vole sous votre nom dans le même salon, la partie est retenue'
  ' à moins que vous ne vous soyez annoncé, et la <b>Protection</b> ne compte que les'
  ' parties que vous avez annoncées. Un nom de jeu revendiqué par deux comptes ne compte'
  ' pour aucun.</p><p>Une <b>&#10003;</b> à côté d&#39;un nom signifie que ce joueur a'
  ' activé la Protection : seules les parties qu&#39;il a annoncées comptent pour lui.'
  ' C&#39;est un classement plus strict et plus lent, et c&#39;est facultatif &mdash; cela'
  ' se trouve dans <a href="/settings">Paramètres</a>.</p>'),

 ("Les clans",
  '<p>Un clan est un groupe de joueurs qui partagent un tag. Sa page montre l&#39;effectif'
  ' classé par niveau, le bilan commun, ses victoires en survie et où le clan'
  ' joue.</p><p><b>Pour en rejoindre un.</b> <a href="/social">Social</a> vous suggère les'
  ' clans dont les membres jouent à peu près à votre niveau, et vous montre tous ceux qui'
  ' acceptent les candidatures. Vous pouvez aussi ouvrir la page d&#39;un clan et appuyer'
  ' sur <b>Demander à rejoindre</b>, ou utiliser un lien d&#39;invitation donné par son'
  ' chef. Dans les deux cas, c&#39;est le chef qui décide. Si votre nom en jeu porte déjà le'
  ' tag du clan au moment de sa création, vous êtes ajouté automatiquement.</p><p><b>Votre'
  ' tag est affiché exactement tel qu&#39;il est écrit</b> &mdash; lettres fantaisie'
  ' comprises. La version en lettres simples ne sert qu&#39;en coulisses, pour que toutes'
  ' les écritures d&#39;un tag comptent comme un seul clan et que la recherche marche dans'
  ' les deux sens. Un chef peut ajouter d&#39;autres écritures du tag dans <a'
  ' href="/myclan">Votre clan</a>, et chaque membre choisit celle qu&#39;il porte dans <a'
  ' href="/account">Votre compte</a>.</p><p><b>Une partie sous le tag de votre clan compte'
  ' pour vous</b>, quelle que soit l&#39;écriture du tag. Seuls les membres de ce clan sont'
  ' reconnus ainsi, et ce qui suit le tag doit être votre nom.</p><p><b>Votre nom de compte,'
  ' c&#39;est vous et rien d&#39;autre.</b> Quand vous rejoignez un clan, le tag quitte'
  ' votre nom de compte et s&#39;affiche à côté comme un badge, si bien que le tag peut'
  ' changer, et votre clan aussi, sans que votre bilan ne bouge. La page du compte demande'
  ' confirmation avant d&#39;enregistrer un nom qui porte un tag.</p><p><b>Les rangs.</b> Un'
  ' chef peut nommer des co-chefs et des modérateurs. Un modérateur retire les membres'
  ' ordinaires ; un co-chef fait tout ce que fait le chef sauf supprimer le clan ou toucher'
  ' à un autre co-chef. Personne ne peut retirer quelqu&#39;un de son propre rang ou'
  ' au-dessus.</p>'),

 ('Un nom déjà présent au classement',
  '<p>Saisissez-le dans <a href="/settings">Paramètres</a> et, s’il n’appartient à personne, il est à vous tout de suite. S’il a déjà un historique, la page vous propose de le <b>réclamer</b>. Prouvez qu’il est à vous en jouant une partie classée en Deathmatch &mdash; la commande <b>/proveclaim</b> du bot Discord vous guide &mdash; ou attendez que [[CONTACT]] l’examine. Tant que la réclamation est ouverte, elle s’affiche sur la page de ce joueur, pour que le vrai propriétaire puisse la signaler.</p>'
  '<p>Il se passe la même chose si un nom déjà au classement <b>se lit</b> comme celui que vous avez tapé &mdash; un nom simple face à une version en lettres décorées. C’est sur cette ligne que vos parties arrivent, donc c’est celle-là qui vous est proposée. S’il s’agit vraiment de quelqu’un d’autre, enregistrez quand même votre nom.</p>'),

 ("Diriger un clan",
  '<p>Les clans sont attribués à la main. Demandez sur la page <a href="/clans">Clans</a>'
  ' et [[CONTACT]] approuve ou refuse sur Discord. En cas de refus, vous pouvez redemander.</p>'
  '<p>Une fois approuvé, vous réclamez votre tag, et un onglet <b>Votre clan</b> apparaît'
  ' avec tout au même endroit : le lien d&#39;invitation, qui attend d&#39;entrer,'
  ' l&#39;effectif, les rangs, la région et la suppression du clan.</p>'),

 ("Langues",
  '<p>Choisissez une langue dans l&#39;en-tête de n&#39;importe quelle page &mdash; English,'
  ' Español, Français, Deutsch, Italiano, Русский, Tiếng Việt ou 中文. Tout le site est'
  ' traduit, cette page comprise. L&#39;anglais est l&#39;original : si une traduction'
  ' sonne bizarrement, c&#39;est là qu&#39;est le sens.</p>'),

 ("Discord",
  '<p>Le bot fait presque tout ce que fait ce site &mdash; classements, votre profil, les'
  ' clans, les demandes et les rangs. Demandez une invitation à [[CONTACT]], puis utilisez'
  ' <b>/help</b> pour voir les commandes.</p>'),

 ("Ce que nous savons de vous",
  '<p><b>Aucune adresse IP n&#39;est conservée.</b> Ni quand vous visitez, ni quand vous'
  ' appuyez sur Jouer, ni quand vous vous connectez.</p>'
  '<p>Se connecter avec Discord nous donne votre identifiant de compte et votre pseudo.'
  ' Google donne un identifiant de compte. C&#39;est tout &mdash; pas d&#39;e-mail, et rien'
  ' qui permette de vous contacter.</p>'
  '<p>Le code du site est public : tout cela peut donc être vérifié plutôt que cru sur'
  ' parole.</p>'),

 ('Questions fréquentes',
  '<div class="qa"><b>J’ai gagné et rien ne s’est passé.</b> Les résultats arrivent une dizaine de minutes après la fin de la partie. Au-delà, c’est en général l’une de ces raisons : la partie a duré moins de dix minutes, vous n’y étiez pas pendant les dix minutes nécessaires, votre score n’a pas atteint le minimum, ou vous avez quitté votre camp alors qu’il perdait et vous étiez encore absent quand il a gagné.<b>Mon nom apparaît deux fois.</b> Une orthographe différente compte comme un autre joueur, car c’est tout ce que le jeu indique. Réclamez celui que vous utilisez vraiment.<b>Le classement a été remis à zéro.</b> Les notes sont encore en test et peuvent être effacées à nouveau. Rien de ce que vous faites n’est perdu ; le classement repart simplement de zéro.<b>Quelque chose semble faux.</b> Dites-le sur <a href="/reports">Signaler</a> ou prévenez [[CONTACT]] sur Discord. Une personne le lit.</div>'),
 ("Divisions",
  '<p>Votre division est votre place parmi tous les joueurs classés du classement général, et non une note : elle bouge donc quand les joueurs autour de vous bougent. Les joueurs encore dans leurs premiers matchs ne sont pas comptés.</p>'
  '[[RANKS]]'),
]
