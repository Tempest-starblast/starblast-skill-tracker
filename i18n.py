# -*- coding: utf-8 -*-
"""Short UI labels in the languages our players actually use.

The English text IS the key. The templates stay readable - {{ t('Player') }}
rather than {{ t('board.col.player') }} - and anything not translated falls
back to the English instead of a blank or a key name.

Labels and buttons only, by decision. The explanatory paragraphs stay in
English so there is one copy of them to keep true; translating those would
mean re-translating on every wording change.

Each language is a list of values in KEYS order, which keeps the file small
enough to read in one screen. The lengths are asserted at import, so a
missing value is a startup error rather than a silently shifted column.
"""

LANGS = [
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("ru", "Русский"),
    ("vi", "Tiếng Việt"),
    ("zh", "中文"),
]
LANG_KEYS = [k for k, _ in LANGS]
DEFAULT_LANG = "en"

KEYS = [
    "Leaderboard", "Play", "Clans", "Report", "Info", "Changelog", "Settings",
    "Sign in", "Player", "Region", "Record", "Win%", "Skill", "Members",
    "Joined", "Clan", "Avg skill", "Gained", "When", "All regions",
    "North America", "Europe", "Asia", "Clear", "Your clan", "Every clan",
    "Not yet ranked", "Add", "Remove", "Ranks", "Set rank", "Player name",
    "Leader", "Co-leader", "Moderator", "Ordinary member", "Delete this clan",
    "Leave this clan", "Apply to join", "Accept", "Deny", "Waiting to join",
    "Save region", "Not set", "Request a clan", "Send request", "Claim it",
    "Redeem", "Your request", "Rank", "Language", "Approve", "Win rate",
    "Search all", "Page",
    "Invite link", "Create link", "Copy", "Revoke", "Accept invite",
]

_VALUES = {
 "es": ["Clasificación","Jugar","Clanes","Reportar","Información","Novedades","Ajustes","Iniciar sesión","Jugador","Región","Registro","% Victorias","Habilidad","Miembros","Se unió","Clan","Habilidad media","Ganado","Cuándo","Todas las regiones","Norteamérica","Europa","Asia","Borrar","Tu clan","Todos los clanes","Aún sin clasificar","Añadir","Quitar","Rangos","Asignar rango","Nombre del jugador","Líder","Colíder","Moderador","Miembro normal","Eliminar este clan","Salir del clan","Solicitar unirse","Aceptar","Rechazar","Esperando para unirse","Guardar región","Sin definir","Solicitar un clan","Enviar solicitud","Reclamar","Canjear","Tu solicitud","Puesto","Idioma","Aprobar","Tasa de victorias","Buscar en todo","Página","Enlace de invitación","Crear enlace","Copiar","Revocar","Aceptar invitación"],
 "fr": ["Classement","Jouer","Clans","Signaler","Infos","Nouveautés","Paramètres","Se connecter","Joueur","Région","Bilan","% Victoires","Niveau","Membres","Rejoint","Clan","Niveau moyen","Gagné","Quand","Toutes les régions","Amérique du Nord","Europe","Asie","Effacer","Votre clan","Tous les clans","Pas encore classé","Ajouter","Retirer","Rangs","Définir le rang","Nom du joueur","Chef","Co-chef","Modérateur","Membre ordinaire","Supprimer ce clan","Quitter ce clan","Demander à rejoindre","Accepter","Refuser","En attente d'entrée","Enregistrer la région","Non défini","Demander un clan","Envoyer la demande","Réclamer","Utiliser le code","Votre demande","Rang","Langue","Approuver","Taux de victoire","Tout chercher","Page","Lien d'invitation","Créer le lien","Copier","Révoquer","Accepter l'invitation"],
 "de": ["Rangliste","Spielen","Clans","Melden","Info","Änderungen","Einstellungen","Anmelden","Spieler","Region","Bilanz","Siegquote","Stärke","Mitglieder","Beigetreten","Clan","Durchschn. Stärke","Gewonnen","Wann","Alle Regionen","Nordamerika","Europa","Asien","Löschen","Dein Clan","Alle Clans","Noch nicht gewertet","Hinzufügen","Entfernen","Ränge","Rang setzen","Spielername","Anführer","Co-Anführer","Moderator","Normales Mitglied","Diesen Clan löschen","Clan verlassen","Beitritt anfragen","Annehmen","Ablehnen","Warten auf Aufnahme","Region speichern","Nicht gesetzt","Clan beantragen","Anfrage senden","Beanspruchen","Einlösen","Deine Anfrage","Rang","Sprache","Genehmigen","Siegquote","Alle durchsuchen","Seite","Einladungslink","Link erstellen","Kopieren","Widerrufen","Einladung annehmen"],
 "it": ["Classifica","Gioca","Clan","Segnala","Info","Novità","Impostazioni","Accedi","Giocatore","Regione","Record","% Vittorie","Abilità","Membri","Iscritto","Clan","Abilità media","Guadagnato","Quando","Tutte le regioni","Nord America","Europa","Asia","Cancella","Il tuo clan","Tutti i clan","Non ancora classificato","Aggiungi","Rimuovi","Ruoli","Imposta ruolo","Nome giocatore","Leader","Co-leader","Moderatore","Membro semplice","Elimina questo clan","Lascia il clan","Chiedi di entrare","Accetta","Rifiuta","In attesa di entrare","Salva regione","Non impostata","Richiedi un clan","Invia richiesta","Rivendica","Riscatta","La tua richiesta","Posizione","Lingua","Approva","Tasso di vittorie","Cerca ovunque","Pagina","Link d'invito","Crea link","Copia","Revoca","Accetta l'invito"],
 "ru": ["Таблица лидеров","Играть","Кланы","Пожаловаться","Информация","Изменения","Настройки","Войти","Игрок","Регион","Счёт","% побед","Навык","Участники","Вступил","Клан","Средний навык","Прирост","Когда","Все регионы","Северная Америка","Европа","Азия","Очистить","Ваш клан","Все кланы","Пока без места","Добавить","Убрать","Ранги","Назначить ранг","Имя игрока","Лидер","Со-лидер","Модератор","Обычный участник","Удалить клан","Покинуть клан","Подать заявку","Принять","Отклонить","Ожидают вступления","Сохранить регион","Не указан","Запросить клан","Отправить запрос","Забрать","Активировать код","Ваш запрос","Место","Язык","Одобрить","Процент побед","Искать везде","Страница","Ссылка-приглашение","Создать ссылку","Копировать","Отозвать","Принять приглашение"],
 "vi": ["Bảng xếp hạng","Chơi","Bang hội","Báo cáo","Thông tin","Thay đổi","Cài đặt","Đăng nhập","Người chơi","Khu vực","Thành tích","% Thắng","Kỹ năng","Thành viên","Đã vào","Bang hội","Kỹ năng TB","Đạt được","Khi nào","Tất cả khu vực","Bắc Mỹ","Châu Âu","Châu Á","Xóa","Bang của bạn","Tất cả bang hội","Chưa xếp hạng","Thêm","Xoá khỏi bang","Cấp bậc","Đặt cấp bậc","Tên người chơi","Bang chủ","Phó bang","Điều hành","Thành viên thường","Xóa bang hội","Rời bang hội","Xin gia nhập","Chấp nhận","Từ chối","Đang chờ vào bang","Lưu khu vực","Chưa đặt","Xin lập bang","Gửi yêu cầu","Nhận bang","Dùng mã","Yêu cầu của bạn","Hạng","Ngôn ngữ","Duyệt","Tỷ lệ thắng","Tìm tất cả","Trang","Liên kết mời","Tạo liên kết","Sao chép","Thu hồi","Chấp nhận lời mời"],
 "zh": ["排行榜","开始游戏","战队","举报","说明","更新日志","设置","登录","玩家","地区","战绩","胜率","实力","成员","加入时间","战队","平均实力","获得","时间","所有地区","北美","欧洲","亚洲","清除","我的战队","所有战队","暂未排名","添加","移除","职位","设置职位","玩家名称","队长","副队长","管理员","普通成员","解散战队","退出战队","申请加入","接受","拒绝","等待加入","保存地区","未设置","申请战队","发送申请","认领","兑换","你的申请","名次","语言","批准","胜率","搜索全部","页","邀请链接","创建链接","复制","撤销","接受邀请"],
}

TRANSLATIONS = {"en": {k: k for k in KEYS}}
for _lang, _vals in _VALUES.items():
    assert len(_vals) == len(KEYS), "%s has %d values, KEYS has %d" % (
        _lang, len(_vals), len(KEYS))
    TRANSLATIONS[_lang] = dict(zip(KEYS, _vals))


def translate(text, lang):
    """The label in `lang`, or the English it was written in."""
    return TRANSLATIONS.get(lang, {}).get(text, text)
