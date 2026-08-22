# -*- coding: utf-8 -*-
"""La página de información en español. El original es info_text_en.py."""

TITLE = "Información"
SUB = "Cómo funciona este sitio, en resumen."
FOOT = '¿Dudas? Pregunta a [[CONTACT]] en Discord.'

CARDS = [
 ("Qué es esto",
  '<p class="lead">Una clasificación de habilidad para el modo por equipos de Starblast.'
  ' Juega partidas por equipos, gana, y tu puntuación sube. No hay nada que instalar ni'
  ' que registrar &mdash; estás en la tabla en cuanto ganes una partida que estemos'
  ' observando.</p>'),

 ("Primeros pasos",
  '<ol>'
  '<li>Abre la pestaña <a href="/play">Jugar</a> y elige una partida marcada como'
  ' observada.</li>'
  '<li>Pulsa <b>Jugar</b>. Tu nombre se copia, listo para pegarlo en Starblast.</li>'
  '<li>Juega la partida. Al terminar, el resultado aparece aquí en menos de un minuto.</li>'
  '</ol>'
  '<p>Eso es todo lo necesario. Iniciar sesión es opcional y solo hace falta para los'
  ' extras de más abajo.</p>'),

 ("Qué partidas cuentan",
  '<p>Solo podemos observar unas pocas partidas a la vez, así que no cuentan todas. Una'
  ' partida se puede observar cuando tiene <b>20 minutos</b>, hasta que llega a los 90'
  ' minutos, y necesita al menos cuatro jugadores.</p>'
  '<p>La pestaña <a href="/play">Jugar</a> muestra exactamente qué salas se están'
  ' observando en este momento. Si una partida no está en esa lista, no se registra nada de'
  ' ella &mdash; y no llega más tarde.</p>'),

 ("Tu puntuación",
  '<p>Todo el mundo empieza en <b>[[ELO]]</b>. Una partida te mueve como mucho <b>[[K]]</b>'
  ' puntos.</p>'
  '<p>Cuánto te mueves depende de a quién ganes. Ganar a un equipo más fuerte da casi todo'
  ' el máximo; ganar a uno mucho más débil no da casi nada. Perder funciona igual pero al'
  ' revés. Dos equipos parejos se mueven exactamente un punto.</p>'
  '<p>La fuerza de un equipo es la media de todos sus jugadores, así que machacar a'
  ' equipos débiles no te subirá &mdash; subir significa ganar a gente que también está'
  ' bien valorada.</p>'),

 ("Completa y media",
  '<p>Si ya estabas en la partida cuando empezamos a observarla, cuenta completa. Si te'
  ' unes a una partida que ya se está observando, también cuenta, pero a <b>la mitad</b>'
  ' &mdash; tanto para ganadores como para perdedores. La pestaña Jugar dice cuál es cuál'
  ' antes de que entres.</p>'),

 ("Dos reglas que conviene saber",
  '<p><b>Irse antes de tiempo no libra de la derrota.</b> A un equipo perdedor se le cobra'
  ' con su plantilla más completa, no con quien siguiera ahí al final.</p>'
  '<p><b>Una puntuación por debajo de [[MINSCORE]] no se valora</b>, ni ganando ni perdiendo. Estar'
  ' sentado en una sala no es jugar.</p>'),

 ("Dos nombres",
  '<p><b>Tu nombre de cuenta</b> es la fila de la clasificación que te pertenece. Ahí vive'
  ' tu puntuación, y no cambia cuando te cambias el nombre en el juego. Se establece en'
  ' <a href="/settings">Ajustes</a>.</p>'
  '<p><b>Tu nombre de juego</b> es como te llames en Starblast ahora mismo. Se pone en la'
  ' página <a href="/play">Jugar</a>, y puedes cambiarlo tantas veces como quieras'
  ' &mdash; sirve para reconocer tu nave en una sala, nada más.</p>'
  '<p>Empiezan siendo el mismo, y para la mayoría siguen siéndolo. Solo se diferencian si'
  ' juegas con otro nombre durante un tiempo.</p>'),

 ("El registro previo y la marca verde",
  '<p>Pulsar <b>Jugar</b> antes de una partida es lo que une los dos nombres. El sitio'
  ' busca en esa sala una nave llamada con tu <b>nombre de juego</b>, decide que esa nave'
  ' eres tú, y pone el resultado en tu <b>nombre de cuenta</b> &mdash; así tu puntuación'
  ' crece en un solo sitio, te llames como te llames en el juego.</p>'
  '<p>Así que mantén el nombre de juego de la página Jugar igual que el de tu nave. Ese es'
  ' el que tiene que coincidir; tu nombre de cuenta no.</p>'
  '<p><b>Si no te registras antes</b>, el resultado cae sin más en el nombre que reportó el'
  ' juego. Eso solo cuenta para ti si ese nombre es tuyo.</p>'
  '<p>Una <b>&#10003;</b> junto a un nombre significa que ese jugador tiene la Protección'
  ' activada: solo le cuentan las partidas en las que se registró antes. Es una puntuación'
  ' más estricta y más lenta, y es opcional &mdash; está en'
  ' <a href="/settings">Ajustes</a>.</p>'),

 ("Clanes",
  '<p>Un clan es un grupo de jugadores que comparten una etiqueta. Su página muestra la'
  ' plantilla ordenada por habilidad, el registro conjunto y dónde juega el clan.</p>'
  '<p><b>Cómo entrar.</b> Abre la página del clan y pulsa <b>Solicitar unirse</b>, o usa un'
  ' enlace de invitación que te dé su líder. En ambos casos decide el líder. Si tu nombre'
  ' en el juego ya lleva la etiqueta del clan cuando este se crea, entras'
  ' automáticamente.</p>'
  '<p><b>Tu etiqueta se muestra exactamente como está escrita</b> &mdash; con letras raras'
  ' y todo. La versión en letras normales solo se usa por dentro, para que todas las formas'
  ' de escribir una etiqueta cuenten como un mismo clan y la búsqueda funcione de las dos'
  ' maneras.</p>'
  '<p><b>Rangos.</b> Un líder puede nombrar colíderes y moderadores. Un moderador quita a'
  ' miembros normales; un colíder hace todo lo que hace el líder salvo eliminar el clan o'
  ' tocar a otro colíder. Nadie puede quitar a alguien de su mismo rango o superior.</p>'),

 ("Un nombre que ya está en la clasificación",
  '<p>Escríbelo en <a href="/settings">Ajustes</a> y, si no es de nadie, es tuyo al'
  ' momento. Si ya tiene un registro, la página te ofrece <b>reclamarlo</b>: pasa a ser'
  ' tuyo la próxima vez que ese nombre gane una partida observada, que es como sabemos que'
  ' de verdad eres tú y no alguien quedándose con tu puntuación.</p>'
  '<p>Pasa lo mismo si un nombre que ya está en la tabla <b>se lee</b> igual que el que has'
  ' escrito &mdash; un nombre normal frente a una versión con letras adornadas. Ahí es'
  ' donde están cayendo tus partidas, así que se te ofrece esa fila. Si de verdad es otra'
  ' persona, guarda tu nombre igualmente.</p>'),

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

 ("Preguntas frecuentes",
  '<div class="qa">'
  '<b>He ganado y no ha pasado nada.</b>'
  ' Lo más probable es que la partida no fuera una de las observadas. La pestaña Jugar las'
  ' lista antes de que entres.'
  '<b>Mi nombre está dos veces en la tabla.</b>'
  ' Una forma distinta de escribirlo cuenta como otro jugador, porque es lo único que'
  ' reporta el juego. Reclama el que de verdad usas.'
  '<b>Se ha reiniciado la clasificación.</b>'
  ' Las puntuaciones todavía están en pruebas y pueden borrarse otra vez. Nada de lo que'
  ' hagas se pierde; la tabla simplemente vuelve a empezar.'
  '<b>Algo parece estar mal.</b>'
  ' Dilo en <a href="/reports">Reportar</a> o cuéntaselo a [[CONTACT]] en Discord. Lo lee'
  ' una persona.'
  '</div>'),
]
