"""P0 exit gate: prove sb_decode.py reproduces the browser hook's decode
byte-for-byte on real captured frames (/tmp/p0_frames.json from
p0_capture.py). Any mismatch fails loudly - a raw client that diverges
here would diverge live."""
import json
import sys

import sb_decode

CAP = sys.argv[1] if len(sys.argv) > 1 else "/tmp/p0_frames.json"
data = json.load(open(CAP))["cap"]

fails = 0
checked = {200: 0, 205: 0, 206: 0}
DEC = {200: sb_decode.decode_scoreboard,
       205: sb_decode.decode_stations,
       206: sb_decode.decode_radar}

for f in data["frames"]:
    op = f["op"]
    mine = DEC[op](f["raw"])
    theirs = f["dec"]
    checked[op] += 1
    if mine != theirs:
        fails += 1
        if fails <= 5:
            print("MISMATCH op %d frame len %d" % (op, len(f["raw"])))
            print("  hook  :", json.dumps(theirs)[:200])
            print("  python:", json.dumps(mine)[:200])

# welcome + a join, if captured
w = data.get("welcome")
if w:
    wm = sb_decode.decode_text(json.dumps({"name": "welcome", "data": w}))
    ok = wm and wm[0] == "welcome" and wm[1]["max_players"] == (w.get("mode") or {}).get("max_players")
    print("welcome decode:", "OK" if ok else "FAIL")
    fails += 0 if ok else 1
for jn in (data.get("joins") or [])[:1]:
    jm = sb_decode.decode_text(json.dumps({"name": "player_name", "data": jn}))
    ok = jm and jm[0] == "join" and jm[1]["id"] == jn.get("id")
    print("join decode   :", "OK" if ok else "FAIL")
    fails += 0 if ok else 1

print()
print("frames checked:", checked)
print("MISMATCHES:", fails)
print("P0 RESULT:", "PASS - decoder is byte-exact" if fails == 0 else "FAIL")
sys.exit(1 if fails else 0)
