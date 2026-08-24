"""Standalone Starblast spectator-frame decoders (P0 of the raw-client plan).

Pure Python, no browser: the exact logic the tracker's in-page hook runs,
lifted out so a raw WebSocket client can decode the same frames. Validated
byte-for-byte against the live hook by tools_p0_validate.py.

The socket carries two channels:
  * text   - JSON 'welcome' (lobby rulebook) and 'player_name' (join events)
  * binary - op 200 scoreboard, 205 station health, 206 camera radar

Every decoder takes a bytes/bytearray/list-of-ints and returns plain data,
or None when the frame is not its opcode / fails the shape check. Shape
checks mirror the hook exactly: a frame that the hook would discard must
decode to None here too, or the raw client would diverge.
"""
import json


def _b(frame):
    """Normalize to a list of ints so bytes, bytearray and JSON arrays all
    decode identically."""
    return list(frame)


def decode_scoreboard(frame):
    """op-200: per-ship board rows, or None.

    Shape: byte0 == 200, byte1 == ship count n, total length == 2 + 8n.
    Each 8-byte record: [id, mapX, mapY, tier<<5|.., scoreLo, scoreHi,
    _, model]. Score is 16-bit little-endian; tier is the top 3 bits of
    byte+3; model 0 means the ship is dead. Order is NOT relied on.
    """
    b = _b(frame)
    if not b or b[0] != 200 or len(b) < 2:
        return None
    n = b[1]
    if len(b) != 2 + 8 * n:
        return None
    rows = []
    for k in range(n):
        o = 2 + 8 * k
        rows.append({"id": b[o],
                     "score": b[o + 4] | (b[o + 5] << 8),
                     "tier": b[o + 3] >> 5,
                     "model": b[o + 7],
                     "mx": b[o + 1], "my": b[o + 2]})
    return rows


def decode_stations(frame):
    """op-205: three 19-byte team blocks, or None.

    Fixed 58-byte frame. Per block at offset 1+19t: [lvl, gemsLo, gemsHi,
    ..., moduleCount, 12x moduleHP]. HP 0 = destroyed, <255 = damaged,
    255 = intact. gems is 16-bit little-endian.
    """
    b = _b(frame)
    if not b or b[0] != 205 or len(b) != 58:
        return None
    st = []
    for t in range(3):
        o = 1 + 19 * t
        weak = dead = 0
        hp12 = []
        nm = min(b[o + 6], 12)
        for i in range(nm):
            hp = b[o + 7 + i]
            hp12.append(hp)
            if hp == 0:
                dead += 1
            elif hp < 255:
                weak += 1
        st.append({"lvl": b[o + 1],
                   "gems": b[o + 2] | (b[o + 3] << 8),
                   "dead": dead, "weak": weak, "n": nm, "mods": hp12})
    return st


def decode_radar(frame):
    """op-206: camera-relative ship blips [[id, x, y], ...], or None.

    Records of 5 bytes from offset 10; only records whose byte+2 == 2 are
    ships. x/y are signed (0-255 recentred to +/-128). id is 16-bit LE.
    """
    b = _b(frame)
    if not b or b[0] != 206:
        return None
    sh = []
    o = 10
    while o + 5 <= len(b):
        if b[o + 2] == 2:
            x = b[o + 3]
            y = b[o + 4]
            if x > 127:
                x -= 256
            if y > 127:
                y -= 256
            sh.append([b[o] | (b[o + 1] << 8), x, y])
        o += 5
    return sh


def decode_text(msg):
    """A text frame: ('welcome', rulebook) or ('join', event) or None.

    welcome -> the distilled lobby config the tracker stores (same shape
    the hook builds). join -> {id, name, hue, ecp} from a player_name
    event. Anything else (or non-JSON) -> None.
    """
    try:
        j = json.loads(msg)
    except (ValueError, TypeError):
        return None
    if not isinstance(j, dict):
        return None
    name = j.get("name")
    data = j.get("data") or {}
    if name == "welcome" and data:
        md = data.get("mode") or {}
        return ("welcome", {
            "version": data.get("version"), "seed": data.get("seed"),
            "servertime": data.get("servertime"),
            "max_players": md.get("max_players"),
            "crystal_value": md.get("crystal_value"),
            "lives": md.get("lives"), "max_level": md.get("max_level"),
            "speed_mod": md.get("speed_mod"),
            "healing_ratio": md.get("healing_ratio"),
            "station_size": md.get("station_size"),
            "crystal_capacity": md.get("crystal_capacity"),
            "teams": [{"faction": t.get("faction"),
                       "base_name": t.get("base_name"),
                       "hue": t.get("hue")}
                      for t in (md.get("teams") or [])]})
    if name == "player_name" and data:
        return ("join", {"id": data.get("id"), "hue": data.get("hue"),
                         "n": str(data.get("player_name") or "")[:32],
                         "c": 1 if data.get("custom") else 0})
    return None


BOT_NAME = "elo bot"

# Team hues seen across lobbies: {0,120,240}, {60,180,300}, {210,330,90}.
# The observer's hue is what team it associates with on the choose-sides
# screen. Owner's rule (24 Aug 2026): the elo bot sits on a DIFFERENT team
# than the "homi is watching" observers. A fixed hue can't guarantee that -
# homi's team varies per lobby - so raw_observer.py (P2) reads homi's hue
# from the player_name burst and picks a hue whose team is not homi's before
# committing. This default is only the pre-burst fallback.
BOT_DEFAULT_HUE = 180


def make_get_name_frame(ship_id):
    """Ask the server for one ship's name. The name burst is PULLED, not
    pushed: after the board (op-200) reveals the ship ids present, the
    client sends one get_name per id and the server answers each with a
    player_name frame. A client that only joins and listens never learns
    names (found 24 Aug 2026 - the browser sends these, our first raw
    client did not)."""
    return json.dumps({"name": "get_name", "data": {"id": int(ship_id)}})


def make_join_frame(sid, player_name=BOT_NAME, hue=BOT_DEFAULT_HUE):
    """The one text frame a raw client sends to spectate a lobby.

    Mirrors the real client's join exactly (field set and order captured
    24 Aug 2026). `create:false` + a spectate-shaped join is what the
    tracker's browser sends; nothing else is transmitted for the life of
    the connection - the client never selects a team, so it never spawns a
    ship and never plays. `player_name` is what other players see the
    observer listed as: "elo bot".
    """
    return json.dumps({"name": "ojct:4", "data": {
        "mode": "join", "player_name": player_name, "hue": hue,
        "preferred": int(sid), "bonus": False, "ecp_key": None,
        "steamid": None,
        "ecp_custom": {"badge": "star", "finish": "alloy", "laser": "1"},
        "create": False, "client_ship_id": "0", "client_tr": 1}})
