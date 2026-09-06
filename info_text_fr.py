# -*- coding: utf-8 -*-
"""La page Infos en français. L'original est info_text_en.py."""

TITLE = "Infos"
SUB = "Comment ce site fonctionne, en bref."
FOOT = 'Des questions ? Demandez à [[CONTACT]] sur Discord.'

CARDS = [
 ("Ce que c'est",
  '<p class="lead">Un classement de niveau pour le mode équipe de Starblast. Jouez des'
  ' parties en équipe, gagnez, et votre niveau monte. Rien à installer, aucune inscription'
  ' &mdash; vous êtes dans le classement dès que vous gagnez une partie que nous'
  ' observons.</p>'),

 ("Pour commencer",
  '<ol>'
  '<li>Ouvrez l&#39;onglet <a href="/play">Jouer</a> et choisissez une partie marquée comme'
  ' suivie.</li>'
  '<li>Appuyez sur <b>Jouer</b>. Votre nom est copié, prêt à coller dans Starblast.</li>'
  '<li>Jouez la partie. À la fin, le résultat apparaît ici en moins d&#39;une minute.</li>'
  '</ol>'
  '<p>C&#39;est tout ce qu&#39;il faut. Se connecter est facultatif et ne sert que pour les'
  ' options ci-dessous.</p>'),

 ("Quelles parties comptent",
  '<p>Désormais, chaque partie en équipe en cours est suivie, dès l&#39;instant où elle'
  ' commence &mdash; il n&#39;y a plus de limite à quelques-unes seulement à la fois. Il'
  ' suffit qu&#39;une partie compte au moins <b>quatre joueurs</b>, et elle est suivie'
  ' jusqu&#39;au bout.</p>'
  '<p>L&#39;onglet <a href="/play">Jouer</a> liste chaque partie en cours et indique si'
  ' l&#39;observateur y est déjà ; un salon tout neuf est repéré en quelques secondes. Si'
  ' une partie est en cours, elle compte.</p>'),

 ("Votre niveau",
  '<p>Tout le monde commence à <b>[[ELO]]</b>. Une partie vous déplace d&#39;au plus'
  ' <b>[[K]]</b> points.</p>'
  '<p>De combien vous bougez dépend de qui vous battez. Battre une équipe plus forte'
  ' rapporte presque le maximum ; en battre une bien plus faible ne rapporte presque rien.'
  ' La défaite fonctionne pareil, à l&#39;envers. Deux équipes de même force bougent'
  ' d&#39;exactement un point.</p>'
  '<p>La force d&#39;une équipe est la moyenne de tous ses joueurs : écraser des'
  ' équipes faibles ne vous fera pas monter &mdash; monter veut dire battre des gens'
  ' eux-mêmes bien classés. Vos coéquipiers comptent aussi : votre variation mélange votre score et la moyenne de votre équipe &mdash; porter des alliés faibles vers la victoire rapporte plus que la même victoire dans une équipe surpuissante, et perdre avec des alliés faibles coûte moins.</p>'),

 ("Pleine et demie",
  '<p>Comme l&#39;observateur suit chaque partie depuis son début, il voit exactement quand'
  ' votre vaisseau est arrivé. Entrez tôt et vous comptez <b>pleinement</b> ; arrivez dans'
  ' une partie déjà bien avancée et elle ne compte qu&#39;à <b>moitié</b> &mdash; pour les'
  ' gagnants comme pour les perdants. Ce qui compte, c&#39;est le moment où vous avez'
  ' vraiment rejoint la partie, pas celui où vous appuyez sur Jouer.</p>'),

 ("Deux règles à connaître",
  '<p><b>Partir tôt n&#39;évite pas la défaite.</b> Une équipe perdante est comptée avec'
  ' son effectif le plus complet, et non avec ceux qui étaient encore là à la fin.</p>'
  '<p><b>Un score inférieur à [[MINSCORE]] n&#39;est pas classé du tout</b>, victoire ou'
  ' défaite. Rester assis dans un salon, ce n&#39;est pas jouer.</p>'),

 ("Deux noms",
  '<p><b>Votre nom de compte</b> est la ligne du classement qui vous appartient. C&#39;est'
  ' là que vit votre niveau, et il ne change pas quand vous vous renommez en jeu. Il se'
  ' règle dans <a href="/settings">Paramètres</a>.</p>'
  '<p><b>Votre nom de jeu</b> est celui que vous portez dans Starblast en ce moment. Il se'
  ' règle sur la page <a href="/play">Jouer</a>, et vous pouvez le changer autant que vous'
  ' voulez &mdash; il sert à reconnaître votre vaisseau dans un salon, rien de plus.</p>'
  '<p>Au départ ce sont les mêmes, et pour la plupart des gens ils le restent. Ils ne'
  ' diffèrent que si vous jouez sous un autre nom pendant un temps.</p>'),

 ("L'annonce avant la partie, et la coche verte",
  '<p>Appuyer sur <b>Jouer</b> avant une partie, c&#39;est ce qui relie les deux noms. Le'
  ' site guette dans ce salon un vaisseau portant votre <b>nom de jeu</b>, décide que ce'
  ' vaisseau c&#39;est vous, et met le résultat sur votre <b>nom de compte</b> &mdash;'
  ' ainsi votre niveau grandit au même endroit, quel que soit votre nom en jeu.</p>'
  '<p>Gardez donc le nom de jeu de la page Jouer identique à celui de votre vaisseau.'
  ' C&#39;est celui-là qui doit correspondre ; pas votre nom de compte.</p>'
  '<p><b>Si vous ne vous annoncez pas</b>, le résultat tombe simplement sur le nom rapporté'
  ' par le jeu. Cela ne compte pour vous que si ce nom est le vôtre.</p>'
  '<p>Une <b>&#10003;</b> à côté d&#39;un nom signifie que ce joueur a activé la Protection :'
  ' seules les parties qu&#39;il a annoncées comptent pour lui. C&#39;est un classement plus'
  ' strict et plus lent, et c&#39;est facultatif &mdash; cela se trouve dans'
  ' <a href="/settings">Paramètres</a>.</p>'),

 ("Les clans",
  '<p>Un clan est un groupe de joueurs qui partagent un tag. Sa page montre l&#39;effectif'
  ' classé par niveau, le bilan commun et où le clan joue.</p>'
  '<p><b>Pour en rejoindre un.</b> Ouvrez la page du clan et appuyez sur <b>Demander à'
  ' rejoindre</b>, ou utilisez un lien d&#39;invitation donné par son chef. Dans les deux'
  ' cas, c&#39;est le chef qui décide. Si votre nom en jeu porte déjà le tag du clan au'
  ' moment de sa création, vous êtes ajouté automatiquement.</p>'
  '<p><b>Votre tag est affiché exactement tel qu&#39;il est écrit</b> &mdash; lettres'
  ' fantaisie comprises. La version en lettres simples ne sert qu&#39;en coulisses, pour'
  ' que toutes les écritures d&#39;un tag comptent comme un seul clan et que la recherche'
  ' marche dans les deux sens.</p>'
  '<p><b>Les rangs.</b> Un chef peut nommer des co-chefs et des modérateurs. Un modérateur'
  ' retire les membres ordinaires ; un co-chef fait tout ce que fait le chef sauf supprimer'
  ' le clan ou toucher à un autre co-chef. Personne ne peut retirer quelqu&#39;un de son'
  ' propre rang ou au-dessus.</p>'),

 ("Un nom déjà présent au classement",
  '<p>Tapez-le dans <a href="/settings">Paramètres</a> et, si personne ne le possède, il'
  ' est à vous aussitôt. S&#39;il a déjà un bilan, la page propose plutôt de le'
  ' <b>réclamer</b> : il devient vôtre la prochaine fois que ce nom gagne une partie'
  ' suivie, ce qui nous confirme que c&#39;est bien vous et non quelqu&#39;un qui se sert'
  ' dans votre niveau.</p>'
  '<p>Même chose si un nom déjà au classement <b>se lit</b> comme celui que vous avez tapé'
  ' &mdash; un nom simple face à une version en lettres fantaisie. C&#39;est là que vos'
  ' parties atterrissent, donc c&#39;est cette ligne qui vous est proposée. Si c&#39;est'
  ' vraiment quelqu&#39;un d&#39;autre, enregistrez votre nom quand même.</p>'),

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

 ("Questions fréquentes",
  '<div class="qa">'
  '<b>J&#39;ai gagné et rien ne s&#39;est passé.</b>'
  ' La partie n&#39;était probablement pas suivie. L&#39;onglet Jouer les liste avant que'
  ' vous entriez.'
  '<b>Mon nom est deux fois au classement.</b>'
  ' Une orthographe différente compte comme un autre joueur, car c&#39;est tout ce que le'
  ' jeu rapporte. Réclamez celui sous lequel vous jouez vraiment.'
  '<b>Le classement a été remis à zéro.</b>'
  ' Les niveaux sont encore en test et peuvent être effacés à nouveau. Rien de ce que vous'
  ' faites n&#39;est perdu ; le classement repart simplement de zéro.'
  '<b>Quelque chose ne va pas.</b>'
  ' Dites-le sur <a href="/reports">Signaler</a> ou prévenez [[CONTACT]] sur Discord.'
  ' C&#39;est lu par une personne.'
  '</div>'),
]
