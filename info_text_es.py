# -*- coding: utf-8 -*-
"""La página de información en español. El original es info_text_en.py."""

TITLE = "Información"
SUB = "Cómo funciona este sitio, en resumen."
SEARCH = "Buscar en esta página…"
NOMATCH = "Nada en esta página coincide con eso."
STALE = ()
FOOT = '¿Dudas? Pregunta a [[CONTACT]] en Discord.'

CARDS = [
 ('Qué es esto',
  '<p class="lead">Una clasificación de habilidad para el modo por equipos de Starblast. Juega partidas por equipos, gana y tu puntuación sube. Nada que instalar ni registrarse &mdash; apareces en la clasificación en cuanto juegas una partida que puntuamos.</p>'),

 ('Primeros pasos',
  '<ol><li>Abre la pestaña <a href="/play">Jugar</a> y elige una partida.</li>'
  '<li>Pulsa <b>Jugar</b>. Tu nombre se copia, listo para pegarlo en Starblast.</li>'
  '<li>Juega. Cuando termine, el resultado aparece aquí en unos diez minutos.</li>'
  '</ol>'
  '<p>Eso es todo. Iniciar sesión es opcional y solo hace falta para los extras de más abajo.</p>'),

 ('Qué partidas cuentan',
  '<p>Se vigila cada partida por equipos en directo, desde el momento en que aparece la sala. No hay límite de cuántas a la vez ni un mínimo de jugadores para que una sala se recoja.</p>'
  '<p>Para <b>puntuar</b>, una partida tiene que durar <b>al menos diez minutos</b>. Las más cortas se graban igualmente y se pueden volver a ver, pero no mueven la puntuación de nadie.</p>'
  '<p>Dentro de una partida puntuada se puntúa a <b>todo el que</b> estuvo en ella <b>diez minutos</b> y alcanzó la puntuación mínima, gane o pierda. Solo cuenta el tiempo que el vigilante vio.</p>'
  '<p>La pestaña <a href="/play">Jugar</a> muestra cada partida en directo y si el vigilante ya está en ella; una sala nueva se recoge en pocos segundos. Si una partida está en directo, cuenta.</p>'
  '<p>El tiempo que pasas en partidas puntuadas se suma en tu perfil &mdash; en total, con las dos últimas semanas al lado. Lo mide el vigilante, así que sigue las mismas reglas que todo lo anterior: una partida sin puntuar, o una sala que nadie vigilaba, no cuenta nada. El reloj empezó el 21 de septiembre de 2026.</p>'),

 ('Tu puntuación',
  '<p>Todos empiezan en <b>[[ELO]]</b>. En tus primeras <b>[[NEWGAMES]]</b> partidas una sola partida puede moverte hasta <b>[[KNEW]]</b> puntos, para que encuentres tu nivel rápido; después, hasta <b>[[KEST]]</b>.</p>'
  '<p>Cuánto te mueves depende de a quién ganas. Ganar a un bando más fuerte da casi el máximo; ganar a uno mucho más débil apenas da nada. Perder funciona igual, al revés.</p>'
  '<p>La fuerza de un equipo es la media de todos sus miembros, así que ganar a equipos débiles no te subirá &mdash; subir significa ganar a gente que tiene una puntuación alta. También cuenta quién está a tu lado: tu cambio mezcla tu propia puntuación con la media de tu equipo, así que llevar a compañeros flojos a la victoria paga más que la misma victoria en un equipo cargado &mdash; y perder junto a compañeros flojos cuesta menos.</p>'),

 ('Completa y media',
  '<p>Como el vigilante sigue cada partida desde el principio, ve exactamente cuándo tu nave se unió al bando que acabó ganando. Si te uniste en la primera mitad de la partida, la victoria cuenta <b>completa</b>. Si fue en la segunda mitad, cuenta <b>como mucho la mitad</b> &mdash; menos cuanto menos tiempo estuviste.</p>'
  '<p>Una derrota siempre cuenta completa: llegar tarde no es una forma de perder menos. Se juzga por cuándo entraste de verdad, no por cuándo pulsaste Jugar.</p>'),

 ('Reglas que conviene saber',
  '<p><b>Hace falta puntuar, no solo estar.</b> Para puntuar tienes que haber llegado a <b>[[MINPEAK]]</b> en algún momento de la partida si tu bando ganó, o a <b>[[MINLOSE]]</b> si perdió. Estar en una sala no es jugar.</p>'
  '<p><b>Irse antes no evita una derrota.</b> Se cobra a todos los que jugaron en el bando perdedor, estuvieran o no al final.</p>'
  '<p><b>Abandonar un bando que parece perdido no te da su remontada.</b> Si tu bando tenía menos de un 25 % de opciones cuando te fuiste, y seguías fuera cuando ganó, más de diez minutos después, la victoria no es tuya. Tu página de cuenta lo explica.</p>'),

 ("Dos nombres",
  '<p><b>Tu nombre de cuenta</b> es la fila de la clasificación que te pertenece. Ahí vive'
  ' tu puntuación, y no cambia cuando te cambias el nombre en el juego. Se establece en <a'
  ' href="/settings">Ajustes</a>.</p><p><b>Tu nombre de juego</b> es como te llames en'
  ' Starblast ahora mismo. Se pone en la página <a href="/play">Jugar</a>, y puedes'
  ' cambiarlo tantas veces como quieras &mdash; así reconocemos tu nave en una sala, y una'
  ' partida jugada con ese nombre cuenta para tu cuenta.</p><p>Empiezan siendo el mismo, y'
  ' para la mayoría siguen siéndolo. Solo se diferencian si juegas con otro nombre durante'
  ' un tiempo.</p>'),

 ("El registro previo y la marca verde",
  '<p>Pulsar <b>Jugar</b> antes de una partida es lo que une los dos nombres. El sitio'
  ' busca en esa sala una nave llamada con tu <b>nombre de juego</b>, decide que esa nave'
  ' eres tú, y pone el resultado en tu <b>nombre de cuenta</b> &mdash; así tu puntuación'
  ' crece en un solo sitio, te llames como te llames en el juego.</p><p>Así que mantén el'
  ' nombre de juego de la página Jugar igual que el de tu nave. Ese es el que tiene que'
  ' coincidir; tu nombre de cuenta no.</p><p><b>Si no te registras antes</b>, una partida'
  ' con tu nombre de juego cuenta para ti igualmente. Lo que añade el registro es la prueba'
  ' de qué nave era la tuya: si otra persona vuela con tu nombre en la misma sala, la'
  ' partida se retiene a menos que te hayas registrado, y la <b>Protección</b> solo cuenta'
  ' las partidas en las que te registraste. Un nombre de juego que reclaman dos cuentas no'
  ' cuenta para ninguna.</p><p>Una <b>&#10003;</b> junto a un nombre significa que ese'
  ' jugador tiene la Protección activada: solo le cuentan las partidas en las que se'
  ' registró antes. Es una puntuación más estricta y más lenta, y es opcional &mdash; está'
  ' en <a href="/settings">Ajustes</a>.</p>'),

 ("Clanes",
  '<p>Un clan es un grupo de jugadores que comparten una etiqueta. Su página muestra la'
  ' plantilla ordenada por habilidad, el registro conjunto, sus victorias en supervivencia y'
  ' dónde juega el clan.</p><p><b>Cómo entrar.</b> <a href="/social">Social</a> te sugiere'
  ' los clanes cuyos miembros juegan más o menos a tu nivel, y te muestra todos los que'
  ' aceptan solicitudes. También puedes abrir la página de un clan y pulsar <b>Solicitar'
  ' unirse</b>, o usar un enlace de invitación que te dé su líder. En ambos casos decide el'
  ' líder. Si tu nombre en el juego ya lleva la etiqueta del clan cuando este se crea,'
  ' entras automáticamente.</p><p><b>Tu etiqueta se muestra exactamente como está'
  ' escrita</b> &mdash; con letras raras y todo. La versión en letras normales solo se usa'
  ' por dentro, para que todas las formas de escribir una etiqueta cuenten como un mismo'
  ' clan y la búsqueda funcione de las dos maneras. Un líder puede añadir otras formas de'
  ' escribir la etiqueta en <a href="/myclan">Tu clan</a>, y cada miembro elige en <a'
  ' href="/account">Tu cuenta</a> cuál llevar.</p><p><b>Una partida con la etiqueta de tu'
  ' clan cuenta para ti</b>, esté escrita como esté. Solo los miembros de ese clan se'
  ' asignan así, y lo que sigue a la etiqueta tiene que ser tu nombre.</p><p><b>Tu nombre de'
  ' cuenta eres solo tú.</b> Al entrar en un clan, la etiqueta sale de tu nombre de cuenta y'
  ' aparece al lado como insignia, así que la etiqueta puede cambiar, y tu clan también, sin'
  ' que tu registro se mueva. La página de la cuenta pregunta antes de guardar un nombre que'
  ' lleve una etiqueta.</p><p><b>Rangos.</b> Un líder puede nombrar colíderes y moderadores.'
  ' Un moderador quita a miembros normales; un colíder hace todo lo que hace el líder salvo'
  ' eliminar el clan o tocar a otro colíder. Nadie puede quitar a alguien de su mismo rango'
  ' o superior.</p>'),

 ('Un nombre que ya está en la clasificación',
  '<p>Escríbelo en <a href="/settings">Ajustes</a> y, si no es de nadie, es tuyo al momento. Si ya tiene un historial, la página te ofrece <b>reclamarlo</b>. Demuestra que es tuyo jugando una partida clasificada de Deathmatch &mdash; el comando <b>/proveclaim</b> del bot de Discord te guía &mdash; o espera a que [[CONTACT]] lo revise. Mientras la reclamación está abierta aparece en la página de ese jugador, para que el dueño real pueda denunciarla.</p>'
  '<p>Lo mismo pasa si un nombre que ya está en la clasificación <b>se lee</b> igual que el que escribiste &mdash; un nombre normal frente a una versión con letras decoradas. Esa fila es donde están cayendo tus partidas, así que te ofrece esa. Si de verdad es otra persona, guarda tu nombre igualmente.</p>'),

 ("Llevar un clan",
  '<p>Los clanes se conceden a mano. Pídelo en la página <a href="/clans">Clanes</a> y'
  ' [[CONTACT]] lo aprueba o lo rechaza en Discord. Si te lo rechazan, puedes volver a'
  ' pedirlo.</p>'
  '<p>Una vez aprobado reclamas tu etiqueta, y aparece una pestaña <b>Tu clan</b> con todo'
  ' en un mismo sitio: el enlace de invitación, quién espera para entrar, la plantilla, los'
  ' rangos, la región y la eliminación del clan.</p>'),

 ("Idiomas",
  '<p>Elige un idioma en la cabecera de cualquier página &mdash; English, Español,'
  ' Français, Deutsch, Italiano, Русский, Tiếng Việt o 中文. Todo el sitio está traducido,'
  ' esta página incluida. El inglés es el original, así que si alguna traducción suena'
  ' rara, ahí está el significado.</p>'),

 ("Discord",
  '<p>El bot hace casi todo lo que hace este sitio &mdash; clasificaciones, tu perfil,'
  ' clanes, solicitudes y rangos. Pide una invitación a [[CONTACT]] y luego usa <b>/help</b>'
  ' para ver los comandos.</p>'),

 ("Qué sabemos de ti",
  '<p><b>No se guarda ninguna dirección IP.</b> Ni al visitar la web, ni al pulsar Jugar,'
  ' ni al iniciar sesión.</p>'
  '<p>Iniciar sesión con Discord nos da tu identificador de cuenta y tu usuario. Google nos'
  ' da un identificador de cuenta. Eso es todo &mdash; sin correo, y sin nada con lo que se'
  ' te pueda contactar.</p>'
  '<p>El código del sitio es público, así que todo esto se puede comprobar en lugar de'
  ' creerlo sin más.</p>'),

 ('Preguntas frecuentes',
  '<div class="qa"><b>Gané y no pasó nada.</b> Los resultados tardan unos diez minutos en llegar después de que termina la partida. Si pasa más tiempo, suele ser una de estas cosas: la partida duró menos de diez minutos, no estuviste en ella los diez minutos que hacen falta, tu puntuación no llegó al mínimo, o dejaste tu bando cuando iba perdiendo y seguías fuera cuando ganó.<b>Mi nombre aparece dos veces.</b> Una grafía distinta cuenta como otro jugador, porque es lo único que informa el juego. Reclama el que usas de verdad.<b>La clasificación se reinició.</b> Las puntuaciones aún están en pruebas y pueden borrarse de nuevo. Nada de lo que hagas se pierde; la clasificación simplemente vuelve a empezar.<b>Algo parece mal.</b> Dilo en <a href="/reports">Reportar</a> o avisa a [[CONTACT]] en Discord. Lo lee una persona.</div>'),
 ("Divisiones",
  '<p>Tu división es tu posición entre todos los jugadores clasificados de la tabla histórica, no una puntuación, así que cambia cuando cambian los jugadores a tu alrededor. Los jugadores que aún están en sus primeras partidas no cuentan.</p>'
  '[[RANKS]]'),
]
