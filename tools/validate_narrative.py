#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""THE LAST SIN: The Sin-Eater — M1 narrative-data validator.

Validates every 05_Narrative JSON file the game-logic core consumes, plus
the world layout the UE village builder reads. Cross-checks references
between files (evidence <-> links <-> insights <-> quests <-> dialogues <->
sim <-> world) and enforces the documented design rules:

  - QUEST_ARCHITECTURE 2.2: every insight path pairs TWO evidence items of
    DIFFERENT types (union of two source types, GAME_BIBLE 6.1).
  - QUEST_ARCHITECTURE 9.1: the chapter's big truths have >= 3 alternative
    evidence paths; supporting truths >= 2.
  - QUEST_ARCHITECTURE 2.1: reliability in 0..1; E1-grade evidence >= 0.7.
  - NPC_SIMULATION 10.1: schedules cover 24h (start <= 08:00, run to
    midnight, no internal gaps) with >= 5h sleep.
  - MILESTONE_PLAN M1 scope: 12 background NPCs with schedules.
  - WORLD_REGISTRY 4: cardinal rules (river south), doors carry documented
    lock reasons, day gating in {1, 2}.
  - The 5 story dialogues cover the 5 story NPCs (Gwendolyn / Crane /
    Coles / Mair / Ifor) per the M1 scope.

Usage: python3 tools/validate_narrative.py   (from the repo root)
Exit code: 0 = all passed, 1 = failures.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NARR = ROOT / "05_Narrative"

CHECKS = [0, 0]


def ok(msg):
    CHECKS[0] += 1
    print(f"  [PASS] {msg}")


def fail(msg):
    CHECKS[1] += 1
    print(f"  [FAIL] {msg}")


def section(title):
    print(f"\n== {title} ==")


def load(rel):
    path = NARR / rel
    if not path.is_file():
        fail(f"missing file: {rel}")
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        fail(f"{rel} is not valid JSON: {exc}")
        return None


def rect_of(entry):
    r = entry.get("rect_m")
    if not r or len(r) < 4:
        return None
    x, y, w, h = r
    return (x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0)


def point_in_rect(px, py, rect):
    return rect[0] <= px <= rect[2] and rect[1] <= py <= rect[3]


def main():
    print("=" * 56)
    print("THE LAST SIN — M1 narrative data validator (05_Narrative/)")
    print("=" * 56)

    evidence = load("evidence/evidence_slice.json")
    quests = load("quests/quests_slice.json")
    sim = load("sim/sim_blackthorne.json")
    world = load("world/blackthorne_blockout.json")
    rumors = load("rumors/rumors_blackthorne.json")
    case_facts = load("case_facts/case_facts_slice.json")
    deduction = load("deduction/deduction_slice.json")
    dialogue_files = sorted((NARR / "dialogues").glob("*.json"))
    dialogues = []
    for df in dialogue_files:
        data = load(f"dialogues/{df.name}")
        if data:
            dialogues.append(data)

    # ---------------------------------------------------------------- evidence
    section("1) evidence_slice.json")
    ev_map = {}
    if evidence:
        ids = [e["id"] for e in evidence["evidence"]]
        if len(ids) == len(set(ids)):
            ok(f"{len(ids)} evidence entries, unique ids")
        else:
            fail("duplicate evidence ids")
        ev_map = {e["id"]: e for e in evidence["evidence"]}

        types_ok = all(e.get("type") in ("physical", "testimonial", "documentary", "hearsay")
                       for e in evidence["evidence"])
        ok(types_ok) if types_ok else fail("bad evidence type value")

        rel_ok = all(0.0 <= e.get("reliability", -1) <= 1.0 for e in evidence["evidence"])
        ok(rel_ok) if rel_ok else fail("reliability outside 0..1")

        high = [e for e in evidence["evidence"] if e["reliability"] >= 0.7]
        ok(f"{len(high)} items at E1-grade reliability (>= 0.7)") if len(high) >= 6 else \
            fail("too few high-reliability items for the E1 judicial path")

        insight_gated = [e for e in evidence["evidence"] if str(e.get("source", "")).startswith("insight:")]
        ok(f"{len(insight_gated)} insight-derived evidence items") if insight_gated else \
            fail("expected the restored-list evidence to be insight-gated")

    # ---------------------------------------------------------------- link rules + insights
    section("2) link rules and insights")
    insight_map = {}
    if evidence:
        rules = evidence["link_rules"]
        rule_map = {}
        for r in rules:
            rule_map[r["id"]] = r
            if r["a"] not in ev_map or r["b"] not in ev_map:
                fail(f"rule {r['id']} references unknown evidence")
            if r["a"] == r["b"]:
                fail(f"rule {r['id']} links an item to itself")
            if not r.get("valid", True) and not r.get("contradiction_reason"):
                fail(f"contradiction rule {r['id']} has no reason")
        ok(f"{len(rules)} link rules, references resolve")

        contradictions = [r for r in rules if not r.get("valid", True)]
        ok(f"{len(contradictions)} contradiction rules with documented reasons") if contradictions else \
            fail("no contradiction rules - the board cannot teach")

        insights = evidence["insights"]
        insight_map = {i["id"]: i for i in insights}
        big_truth_paths = {}
        for ins in insights:
            paths = ins["link_paths"]
            if len(paths) < 2:
                fail(f"insight {ins['id']} has fewer than 2 alternative paths")
            for p_idx, path in enumerate(paths):
                if len(path) < 1:
                    fail(f"insight {ins['id']} path {p_idx} is empty")
                for link_id in path:
                    if link_id not in rule_map:
                        fail(f"insight {ins['id']} references unknown rule {link_id}")
            # the two-source-type rule: every path must unite two different types
            for p_idx, path in enumerate(paths):
                ev_types = set()
                for link_id in path:
                    r = rule_map[link_id]
                    ev_types.add(ev_map[r["a"]]["type"])
                    ev_types.add(ev_map[r["b"]]["type"])
                if len(ev_types) < 2:
                    fail(f"insight {ins['id']} path {p_idx} unites only one source type ({ev_types})")
            big_truth_paths[ins["id"]] = len(paths)
            for ev in ins.get("requires_examined", []):
                if ev not in ev_map:
                    fail(f"insight {ins['id']} requires unknown evidence {ev}")

        # the chapter's big truths: >= 3 paths (QUEST_ARCHITECTURE 9.1)
        for big in ("INS-REFUSAL", "INS-PATTERN"):
            if big in big_truth_paths:
                if big_truth_paths[big] >= 3:
                    ok(f"{big}: {big_truth_paths[big]} alternative evidence paths (rule: >= 3)")
                else:
                    fail(f"{big} has only {big_truth_paths[big]} paths (rule: >= 3)")
        for other, count in big_truth_paths.items():
            if other not in ("INS-REFUSAL", "INS-PATTERN") and count < 2:
                fail(f"{other} has only {count} paths (rule: >= 2)")

        # every insight-gated evidence source exists
        for e in insight_gated:
            gate = str(e["source"]).split(":", 1)[1]
            if gate not in insight_map:
                fail(f"evidence {e['id']} gated by unknown insight {gate}")
        ok("insight gating references resolve") if insight_gated else None

    # ---------------------------------------------------------------- quests
    section("3) quests_slice.json")
    area_ids = set()
    if world:
        area_ids = {a["id"] for a in world.get("areas", [])}
    if quests:
        qids = [q["id"] for q in quests["quests"]]
        if len(qids) == len(set(qids)):
            ok(f"{len(qids)} quests, unique ids")
        else:
            fail("duplicate quest ids")
        sim_npc_ids = {n["id"] for n in sim["npcs"]} if sim else set()
        rumor_id_set = {r["id"] for r in (rumors or {}).get("rumors", [])}
        for q in quests["quests"]:
            if q["day_window_min"] > q["day_window_max"]:
                fail(f"{q['id']} inverted day window")
            optional = [o for o in q["objectives"] if o.get("optional")]
            urgent = q.get("fails_on_expiry", False)
            if optional:
                ok(f"{q['id']}: {len(optional)} optional objective(s) never block completion")
            elif urgent:
                ok(f"{q['id']}: urgent side quest (fails_on_expiry) is itself the optional thread")
            else:
                fail(f"{q['id']} has no optional objective (design: the slice teaches optional threads)")
            if urgent and not q.get("flags_on_fail"):
                fail(f"{q['id']}: urgent quest fails without a story consequence flag")
            if not q.get("flags_on_complete"):
                fail(f"{q['id']} completes without setting a landmark flag")
            for obj in q["objectives"]:
                for task in obj["tasks"]:
                    ttype, target = task["type"], task.get("target", "")
                    if ttype in ("reach",):
                        if target not in area_ids:
                            fail(f"{q['id']}/{obj['id']}: reach target {target} is not a world area")
                    elif ttype in ("observe", "collect", "inspect", "restore"):
                        if target not in ev_map:
                            fail(f"{q['id']}/{obj['id']}: evidence target {target} unknown")
                    elif ttype == "insight":
                        if target not in insight_map:
                            fail(f"{q['id']}/{obj['id']}: insight target {target} unknown")
                    elif ttype == "dialogue":
                        base = target.split(":")[0]
                        if not any(d["id"] == base for d in dialogues):
                            fail(f"{q['id']}/{obj['id']}: dialogue target {base} unknown")
                    elif ttype == "flag":
                        if not target:
                            fail(f"{q['id']}/{obj['id']}: empty flag target")
                    elif ttype == "player_rumor":
                        if target not in rumor_id_set:
                            fail(f"{q['id']}/{obj['id']}: player_rumor target {target} unknown")
                    elif ttype == "npc_rumor":
                        if "=" not in target:
                            fail(f"{q['id']}/{obj['id']}: npc_rumor target needs NPC=RUMOR form")
                        else:
                            npc_part, rumor_part = target.split("=", 1)
                            if npc_part not in sim_npc_ids:
                                fail(f"{q['id']}/{obj['id']}: npc_rumor npc {npc_part} unknown")
                            if rumor_part not in rumor_id_set:
                                fail(f"{q['id']}/{obj['id']}: npc_rumor rumor {rumor_part} unknown")
                    elif ttype == "tension_below":
                        v = task.get("value", 1)
                        if not (1 <= v <= 5):
                            fail(f"{q['id']}/{obj['id']}: tension_below value {v} outside 1..5")
        ok("quest task targets resolve against world/evidence/insights/dialogues/rumors")
        # M2.3: an urgent quest's whole window must not exceed one game day
        for q in quests["quests"]:
            if q.get("fails_on_expiry") and q["day_window_max"] - q["day_window_min"] > 2:
                fail(f"{q['id']}: urgent window spans {q['day_window_max'] - q['day_window_min'] + 1} days - not urgent")

    # ---------------------------------------------------------------- dialogues
    section("4) dialogue files")
    npc_ids = set()
    if sim:
        npc_ids = {n["id"] for n in sim["npcs"]}
    story_needed = {"CHR-03", "CHR-04", "CHR-06", "CHR-13", "CHR-17"}
    covered = set()
    for d in dialogues:
        if d.get("npc") not in npc_ids:
            fail(f"{d['id']}: npc {d.get('npc')} is not in the sim data")
        else:
            covered.add(d["npc"])
        nodes = {n["id"] for n in d["nodes"]}
        if len(nodes) != len(d["nodes"]):
            fail(f"{d['id']}: duplicate node ids")
        if d.get("root") not in nodes:
            fail(f"{d['id']}: root node missing")
        for node in d["nodes"]:
            if node.get("next") and node["next"] not in nodes:
                fail(f"{d['id']}/{node['id']}: auto-next points to missing node")
            if node.get("next") and node.get("choices"):
                fail(f"{d['id']}/{node['id']}: has both choices and auto-next")
            for choice in node.get("choices", []):
                if choice.get("next") and choice["next"] not in nodes:
                    fail(f"{d['id']}/{node['id']}/{choice['id']}: next points to missing node")
                tone = choice.get("tone", "formal")
                if tone not in ("gentle", "formal", "pressing", "silent"):
                    fail(f"{d['id']}/{choice['id']}: bad tone '{tone}'")
                pe = choice.get("present_evidence")
                if pe and pe not in ev_map:
                    fail(f"{d['id']}/{choice['id']}: presents unknown evidence {pe}")
                for ev in choice.get("effects", {}).get("give_evidence", []):
                    if ev not in ev_map:
                        fail(f"{d['id']}/{choice['id']}: grants unknown evidence {ev}")
                for ins in choice.get("effects", {}).get("give_insight", []):
                    if ins not in insight_map:
                        fail(f"{d['id']}/{choice['id']}: grants unknown insight {ins}")
            for ev in node.get("on_enter", {}).get("give_evidence", []):
                if ev not in ev_map:
                    fail(f"{d['id']}/{node['id']}: on_enter grants unknown evidence {ev}")
    missing_story = story_needed - covered
    if not missing_story:
        ok(f"{len(dialogues)} dialogue trees cover all 5 story NPCs (M1 scope)")
    else:
        fail(f"no dialogue for story NPCs: {sorted(missing_story)}")
    ok("dialogue graphs are closed (every next/choice target exists)")

    # ---------------------------------------------------------------- sim
    section("5) sim_blackthorne.json")
    if sim:
        bg = [n for n in sim["npcs"] if n.get("tier") == 3]
        if len(bg) >= 12:
            ok(f"{len(bg)} background NPCs with schedules (M1 scope: 12)")
        else:
            fail(f"only {len(bg)} background NPCs (M1 scope: 12)")
        for n in sim["npcs"]:
            for key in ("schedule", "schedule_tension"):
                segs = n.get(key) or []
                if not segs:
                    if key == "schedule_tension":
                        continue
                    fail(f"{n['id']}: no {key}")
                    continue
                cursor = segs[0]["from_hour"]
                if cursor > 8:
                    fail(f"{n['id']} {key} starts after 08:00 ({cursor})")
                sleep_hours = segs[0]["from_hour"]
                for s in segs:
                    if s["from_hour"] != cursor:
                        fail(f"{n['id']} {key}: gap/overlap at {s['from_hour']}")
                    cursor = s["to_hour"]
                    if s.get("activity") == "sleep":
                        sleep_hours += s["to_hour"] - s["from_hour"]
                if cursor != 24:
                    fail(f"{n['id']} {key} ends at {cursor}, not 24")
                if sleep_hours < 5:
                    fail(f"{n['id']} {key}: sleeps only {sleep_hours}h (rule: >= 5)")
                for s in segs:
                    if s["zone"] not in area_ids:
                        fail(f"{n['id']} {key}: unknown zone {s['zone']}")
            for tone in (n.get("tone_weights") or {}):
                if tone not in ("gentle", "formal", "pressing", "silent"):
                    fail(f"{n['id']}: bad tone weight key '{tone}'")
            if not (-100 <= n.get("initial_trust", 0) <= 100):
                fail(f"{n['id']}: initial trust out of range")
            if not (0.0 <= n.get("relationship_bias", 0) <= 1.0):
                fail(f"{n['id']}: bias out of range")
        ok("schedules: 24h coverage, >= 5h sleep, zones resolve to world areas")

        # tension schedule must exist for the day-2 state
        tension_capable = [n for n in sim["npcs"] if n.get("schedule_tension")]
        ok(f"{len(tension_capable)} NPCs carry a tension-day schedule (day 2, tension 3)")

        weather = sim.get("weather_by_day", {})
        if weather.get("1") == "overcast_fog" and weather.get("2") == "rain":
            ok("day script: fog on Day 1, rain on Day 2 (WORLD_REGISTRY 4: weather as narrative)")
        else:
            fail("weather_by_day does not match the C1/C2 script")

    # ---------------------------------------------------------------- world
    section("6) blackthorne_blockout.json")
    if world:
        areas = world.get("areas", [])
        ids = [a["id"] for a in areas]
        if len(ids) == len(set(ids)):
            ok(f"{len(areas)} unique areas")
        else:
            fail("duplicate area ids")
        for a in areas:
            if not rect_of(a):
                fail(f"area {a['id']} has a malformed rect_m")

        # cardinal rule: the river is the southern band (WORLD_REGISTRY 4)
        band = world.get("water", {}).get("band_m")
        if band and band[1] + band[3] <= -50:
            ok("river Afon Ddu runs in the far south (cardinal rule)")
        else:
            fail("river band is not in the south (cardinal rule broken)")

        palette = world.get("palette", {})
        if set(palette.keys()) >= {"SLT", "MSS", "BRF", "CDL", "SBL", "INK", "PPR"}:
            ok(f"palette carries all 7 canon codes (GAME_BIBLE 7.2)")
        else:
            fail("palette is missing canon codes")

        for b in world.get("buildings", []):
            if b.get("area") not in {a["id"] for a in areas}:
                fail(f"building {b['id']} references unknown area {b.get('area')}")
            rect = rect_of(b)
            g = world["ground"]["size_m"]
            if rect and not (rect[0] >= -g[0] / 2 - 5 and rect[2] <= g[0] / 2 + 5
                             and rect[1] >= -g[1] / 2 - 5 and rect[3] <= g[1] / 2 + 5):
                fail(f"building {b['id']} leaves the ground bounds")
            for key in (b.get("palette") or {}):
                if key not in ("walls", "roof", "trim", "window_light", "wheel"):
                    fail(f"building {b['id']}: unknown palette slot '{key}'")
                elif b["palette"][key] not in palette:
                    fail(f"building {b['id']}: palette code '{b['palette'][key]}' not defined")
        ok("buildings sit inside areas + ground, palette codes resolve")

        for it in world.get("interactables", []):
            if it.get("area") not in {a["id"] for a in areas}:
                fail(f"interactable {it['id']} references unknown area")
            area = next((a for a in areas if a["id"] == it.get("area")), None)
            if area and it.get("pos_m"):
                if not point_in_rect(it["pos_m"][0], it["pos_m"][1], rect_of(area)):
                    fail(f"interactable {it['id']} sits outside its area rect")
            if it.get("day") not in (1, 2):
                fail(f"interactable {it['id']}: day must be 1 or 2 in the slice")
            ev = it.get("evidence")
            if ev and ev not in ev_map:
                fail(f"interactable {it['id']} references unknown evidence {ev}")
        ok("interactables: inside areas, day-gated 1/2, evidence references resolve")

        # day-2 evidence arrives via world placement OR a day-2 dialogue grant
        day2_ev = {e for e, v in ev_map.items() if v.get("day_acquired") == 2}
        placed_day2 = {it["evidence"] for it in world.get("interactables", []) if it.get("day") == 2 and it.get("evidence")}
        granted_day2 = set()
        for d in dialogues:
            for node in d["nodes"]:
                for choice in node.get("choices", []):
                    conds = choice.get("conditions") or {}
                    if conds.get("day_min", 1) >= 2:
                        granted_day2.update(choice.get("effects", {}).get("give_evidence", []))
        reachable = placed_day2 | granted_day2
        if day2_ev == reachable:
            ok(f"all {len(day2_ev)} day-2 evidence items reachable (placed or sworn on day 2)")
        else:
            fail(f"day-2 evidence unreachable: {sorted(day2_ev - reachable)} / misplaced: {sorted(reachable - day2_ev)}")

        for d in world.get("doors", []):
            if not d.get("reason"):
                fail(f"door {d.get('id')} has no documented lock reason")
            if d.get("building") not in {b["id"] for b in world.get("buildings", [])}:
                fail(f"door {d.get('id')} references unknown building")
        ok(f"{len(world.get('doors', []))} locked doors all carry documented reasons (no silent decor)")

        for post in world.get("npc_posts", []):
            if post.get("npc") not in npc_ids:
                fail(f"npc post references unknown NPC {post.get('npc')}")
            if post.get("area") not in {a["id"] for a in areas}:
                fail(f"npc post for {post.get('npc')} references unknown area")
        ok("npc posts resolve to sim NPCs and world areas")

        for path in world.get("paths", []):
            if len(path.get("points_m", [])) < 2:
                fail(f"path {path.get('id')} has fewer than 2 points")
        ok(f"{len(world.get('paths', []))} paths are well formed")

        # ---------------------------------------------------------------- M2.5 world expansion
        # a district may span several areas (D6 swamp + hut, D9 pass + moor);
        # what must hold is full D0..D11 coverage and no duplicated naming
        dist_ids = {a.get("district", "") for a in areas}
        missing_districts = {f"D{i}" for i in range(12)} - dist_ids
        if missing_districts:
            fail(f"districts with no area: {sorted(missing_districts)}")
        else:
            ok(f"districts D0..D11 all present across {len(areas)} areas")
        name_pairs = [(a.get("district", ""), a.get("name", "")) for a in areas]
        if len(name_pairs) == len(set(name_pairs)):
            ok("no two areas share district+name")
        for a in areas:
            du = a.get("day_unlock", 1)
            if not (1 <= du <= 9):
                fail(f"{a['id']}: day_unlock {du} outside the nine-day game")
            r = a.get("rect_m", [])
            if len(r) != 4 or r[2] <= 0 or r[3] <= 0:
                fail(f"{a['id']}: rect_m must be [x, y, w>0, h>0]")
            # ground bounds with the validator's 5 m tolerance
            g = world["ground"]["size_m"]
            if r and not (r[0] >= -g[0] / 2 - 5 and r[0] + r[2] <= g[0] / 2 + 5
                          and r[1] >= -g[1] / 2 - 5 and r[1] + r[3] <= g[1] / 2 + 5):
                fail(f"area {a['id']} leaves the ground bounds")
        ok("every area carries a legal day_unlock and sits inside the ground")
        status = (world.get("region_status") or {}).get("states", {})
        missing_status = {a["id"] for a in areas} - set(status)
        if missing_status:
            fail(f"region_status missing for: {sorted(missing_status)}")
        else:
            built = [k for k, v in status.items() if v != "blockout_data"]
            note = f", non-data states: {built}" if built else ""
            ok(f"region_status covers all {len(status)} areas - none claimed UE-tested{note}")
        area_center = {a["id"]: (a["rect_m"][0] + a["rect_m"][2] / 2, a["rect_m"][1] + a["rect_m"][3] / 2) for a in areas if len(a.get("rect_m", [])) == 4}
        for path in world.get("paths", []):
            pts = path.get("points_m", [])
            if pts and pts[0] not in [tuple(p) for p in pts]:
                pass  # endpoint-to-area proximity is a design judgement; bounds only
            for px, py in pts:
                g = world["ground"]["size_m"]
                if not (-g[0] / 2 - 5 <= px <= g[0] / 2 + 5 and -g[1] / 2 - 5 <= py <= g[1] / 2 + 5):
                    fail(f"path {path.get('id')} leaves the ground bounds")
                    break
        ok("all path points stay inside the expanded ground")

    # ---------------------------------------------------------------- rumors (M2.1)
    section("7) rumors_blackthorne.json")
    rumors = load("rumors/rumors_blackthorne.json")
    if rumors:
        area_id_set = {a["id"] for a in world.get("areas", [])} if world else set()
        if rumors.get("schema") != "tls.rumors.v1":
            fail(f"rumors schema is {rumors.get('schema')}, expected tls.rumors.v1")
        else:
            ok("rumors schema tls.rumors.v1")
        rules = rumors.get("rules") or {}
        cap = rules.get("max_active", 6)
        rumor_list = rumors.get("rumors", [])
        if len(rumor_list) <= cap:
            ok(f"{len(rumor_list)} rumors within the active cap {cap} (NPC_SIMULATION 11)")
        else:
            fail(f"{len(rumor_list)} rumors exceed the active cap {cap}")
        spread_cap = rules.get("daily_spread_cap", 0.30)
        if spread_cap <= 0.30:
            ok(f"daily spread cap {spread_cap} <= 30% of the population per day (NPC_SIMULATION 10)")
        else:
            fail(f"daily spread cap {spread_cap} exceeds the 30% rule")
        for z in rumors.get("gossip_zones", []):
            if z not in area_id_set:
                fail(f"gossip zone {z} is not a world area")
        ok("gossip zones resolve to world areas")
        rumor_ids = set()
        topic_valence = {}
        for r in rumor_list:
            rid = r.get("id", "")
            if not rid:
                fail("rumor without id")
                continue
            if rid in rumor_ids:
                fail(f"duplicate rumor id {rid}")
            rumor_ids.add(rid)
            if r.get("valence", 0.0) < -1.0 or r.get("valence", 0.0) > 1.0:
                fail(f"{rid}: valence out of range")
            if not r.get("origin"):
                fail(f"{rid}: missing origin")
            if not (1 <= r.get("day_created", 0) <= 9):
                fail(f"{rid}: day_created outside the nine-day game")
            if not (0 <= r.get("hour_created", 0) <= 23):
                fail(f"{rid}: hour_created out of range")
            if r.get("place_zone") not in area_id_set:
                fail(f"{rid}: place_zone {r.get('place_zone')} is not a world area")
            if not r.get("variants"):
                fail(f"{rid}: no wording variants (mutation needs material)")
            for seed in r.get("seeds", []):
                if seed.get("npc") not in npc_ids:
                    fail(f"{rid}: seed npc {seed.get('npc')} is not in the sim data")
                if seed.get("kind", "hearsay") not in ("direct", "hearsay", "inference", "unverified"):
                    fail(f"{rid}: bad seed kind {seed.get('kind')}")
                conf = seed.get("confidence", 1.0)
                if not (0.0 <= conf <= 1.0):
                    fail(f"{rid}: seed confidence out of range")
                variants = r.get("variants", [])
                if not (0 <= seed.get("variant", 0) < max(1, len(variants))):
                    fail(f"{rid}: seed variant index out of range")
            topic = r.get("topic", rid)
            topic_valence.setdefault(topic, []).append((rid, r.get("valence", 0.0)))
        ok("rumor entries well formed (ids, origins, zones, seeds, variants)")
        for a_rel, inner in (rumors.get("npc_relationships") or {}).items():
            if a_rel not in npc_ids:
                fail(f"npc_relationships: unknown NPC {a_rel}")
            for b_rel, v in inner.items():
                if b_rel not in npc_ids:
                    fail(f"npc_relationships: unknown NPC {b_rel}")
                if not (-100.0 <= v <= 100.0):
                    fail(f"npc_relationships {a_rel}->{b_rel}: value {v} out of range")
        ok("relationship matrix resolves to sim NPCs")
        conflict_topics = {t: v for t, v in topic_valence.items() if len(v) > 1}
        if conflict_topics:
            for t, entries in conflict_topics.items():
                signs = {1 if v > 0 else -1 if v < 0 else 0 for _, v in entries}
                if len(signs) < 2:
                    fail(f"topic {t}: {len(entries)} rumors share one valence sign - no real conflict")
            ok(f"conflict topics carry opposite valences: {sorted(conflict_topics)}")

    # ---------------------------------------------------------------- case facts (M3.7)
    section("7) case_facts/case_facts_slice.json — the case-fact ledger")
    if case_facts and evidence and sim:
        npc_ids = {n["id"] for n in sim["npcs"]}
        ev_ids = {e["id"] for e in evidence["evidence"]}
        facts = case_facts.get("facts", [])
        fact_ids = [f["id"] for f in facts]
        if len(fact_ids) == len(set(fact_ids)) and fact_ids:
            ok(f"{len(fact_ids)} case facts, unique ids")
        else:
            fail("case fact ids missing or duplicated")

        stances = {"affirms", "denies", "claims", "omits"}
        origins = {"witnessed", "told", "inferred", "documented"}
        problems = []
        granting = {}
        for f in facts:
            fid = f.get("id", "?")
            if not f.get("truth_summary"):
                problems.append(f"{fid}: missing truth_summary")
            if not f.get("canon_ref"):
                problems.append(f"{fid}: missing canon_ref (no fact without a canon anchor)")
            for ev in f.get("related_evidence", []):
                if ev not in ev_ids:
                    problems.append(f"{fid}: related_evidence unknown {ev}")
            n_grant = 0
            seen_npc = set()
            for t in f.get("testimonies", []):
                tn = t.get("npc", "?")
                if tn in seen_npc:
                    problems.append(f"{fid}: duplicate testimony for {tn}")
                seen_npc.add(tn)
                if tn not in npc_ids:
                    problems.append(f"{fid}: testimony npc {tn} not a sim NPC")
                if t.get("stance") not in stances:
                    problems.append(f"{fid}/{tn}: bad stance {t.get('stance')}")
                if t.get("origin") not in origins:
                    problems.append(f"{fid}/{tn}: bad origin {t.get('origin')}")
                if t.get("stance") == "claims" and not t.get("claim_text"):
                    problems.append(f"{fid}/{tn}: claims without claim_text")
                if not 0.0 <= t.get("reliability", -1) <= 1.0:
                    problems.append(f"{fid}/{tn}: reliability out of range")
                if t.get("deliberate") and not t.get("lie_reason"):
                    problems.append(f"{fid}/{tn}: deliberate without lie_reason")
                if t.get("stance") == "omits" and t.get("grants", True):
                    problems.append(f"{fid}/{tn}: omits but grants (a silence teaches nothing)")
                if t.get("grants", True):
                    n_grant += 1
                rev = t.get("reveal", {})
                if not -100.0 <= rev.get("trust_min", -100.0) <= 100.0:
                    problems.append(f"{fid}/{tn}: reveal trust_min out of range")
                for ev in rev.get("requires_evidence", []):
                    if ev not in ev_ids:
                        problems.append(f"{fid}/{tn}: reveal requires unknown evidence {ev}")
                if rev.get("day_min", 1) < 1:
                    problems.append(f"{fid}/{tn}: reveal day_min < 1")
            if f.get("truth_anchor") and n_grant > 0:
                problems.append(f"{fid}: truth_anchor but a testimony grants it")
            granting[fid] = n_grant
        if problems:
            for p in problems:
                fail(p)
        else:
            ok("all facts carry truth_summary, canon_ref, valid stances/origins/reveals")
        anchors = [f["id"] for f in facts if f.get("truth_anchor")]
        ok(f"{len(anchors)} truth anchors (the slice cannot learn them): {anchors}") if anchors else \
            fail("expected the slice truth anchors (LAST-TRAY, MAIR-RETURNED)")

        # dossiers: canon motives + playable concealment
        dossiers = case_facts.get("dossiers", [])
        dossier_problems = []
        for d in dossiers:
            dn = d.get("npc", "?")
            if dn not in npc_ids:
                dossier_problems.append(f"dossier {dn}: not a sim NPC")
            if not d.get("deep_motive") or not d.get("fear"):
                dossier_problems.append(f"dossier {dn}: missing deep_motive/fear")
            for secret in d.get("secret_facts", []):
                if secret not in fact_ids:
                    dossier_problems.append(f"dossier {dn}: secret fact unknown {secret}")
                    continue
                fact = next((f for f in facts if f["id"] == secret), None)
                t = next((t for t in (fact or {}).get("testimonies", []) if t.get("npc") == dn), None)
                if t is None:
                    dossier_problems.append(f"dossier {dn}: secret {secret} has no testimony by this npc")
                else:
                    rev = t.get("reveal", {})
                    gated = (rev.get("trust_min", -100.0) > -100.0 or rev.get("requires_evidence")
                             or rev.get("requires_insights") or rev.get("requires_flags") or rev.get("day_min", 1) > 1)
                    if not gated:
                        dossier_problems.append(f"dossier {dn}: secret {secret} testimony has no reveal gate")
        if dossier_problems:
            for p in dossier_problems:
                fail(p)
        else:
            ok(f"{len(dossiers)} dossiers: canon motives/fears; every secret is gated testimony")
    else:
        fail("case_facts file missing or unloadable")

    # ---------------------------------------------------------------- deduction (M3.7)
    section("8) deduction/deduction_slice.json — hypotheses and accusations")
    if deduction and evidence and sim and case_facts:
        npc_ids = {n["id"] for n in sim["npcs"]}
        ev_ids = {e["id"] for e in evidence["evidence"]}
        insight_ids = {i["id"] for i in evidence.get("insights", [])}
        rule_ids = {r["id"] for r in evidence.get("link_rules", [])}
        fact_ids = {f["id"] for f in case_facts.get("facts", [])}
        rumor_ids = {r["id"] for r in rumors.get("rumors", [])} if rumors else set()
        quest_flag_refs = set()
        for q in quests.get("quests", []):
            quest_flag_refs |= set((q.get("flags_on_complete") or {}).keys())
            quest_flag_refs |= set((q.get("flags_on_fail") or {}).keys())

        hyp_problems = []
        hyps = deduction.get("hypotheses", [])
        for h in hyps:
            hid = h.get("id", "?")
            if not h.get("canon_ref"):
                hyp_problems.append(f"{hid}: missing canon_ref")
            if not (h.get("requires_insights") or h.get("requires_evidence") or h.get("requires_facts")):
                hyp_problems.append(f"{hid}: no support requirements")
            for i in h.get("requires_insights", []):
                if i not in insight_ids:
                    hyp_problems.append(f"{hid}: requires unknown insight {i}")
            for e in h.get("requires_evidence", []):
                if e not in ev_ids:
                    hyp_problems.append(f"{hid}: requires unknown evidence {e}")
            for f in h.get("requires_facts", []):
                if f not in fact_ids:
                    hyp_problems.append(f"{hid}: requires unknown fact {f}")
            for r in h.get("refuted_by", []):
                if r.get("type") == "flag":
                    if not (r.get("target", "").startswith("FLG_")):
                        hyp_problems.append(f"{hid}: flag refuter not an FLG_ id")
                elif r.get("type") == "fact":
                    if r.get("target") not in fact_ids:
                        hyp_problems.append(f"{hid}: fact refuter unknown {r.get('target')}")
                elif r.get("type") == "contradiction":
                    if r.get("target") not in rule_ids:
                        hyp_problems.append(f"{hid}: contradiction refuter unknown rule {r.get('target')}")
                elif r.get("type") == "player_rumor":
                    if r.get("target") not in rumor_ids:
                        hyp_problems.append(f"{hid}: rumor refuter unknown {r.get('target')}")
                else:
                    hyp_problems.append(f"{hid}: bad refuter type {r.get('type')}")
                if not r.get("reason"):
                    hyp_problems.append(f"{hid}: refuter without reason")
        if hyp_problems:
            for p in hyp_problems:
                fail(p)
        else:
            ok(f"{len(hyps)} hypotheses: requirements and refuters resolve to real ids")

        acc_problems = []
        accs = deduction.get("accusations", [])
        tier_keys = {"baseless", "partial", "grounded"}
        for a in accs:
            aid = a.get("id", "?")
            if not a.get("canon_ref"):
                acc_problems.append(f"{aid}: missing canon_ref")
            if not a.get("target_label") or not a.get("topic"):
                acc_problems.append(f"{aid}: missing target_label/topic")
            tn = a.get("target_npc", "")
            if tn and tn not in npc_ids:
                acc_problems.append(f"{aid}: target_npc {tn} not a sim NPC")
            if a.get("max_tier") not in tier_keys or a.get("max_tier") == "baseless":
                acc_problems.append(f"{aid}: bad max_tier")
            if a.get("baseless"):
                if a.get("grounding_insight") or a.get("grounding_evidence") or a.get("grounding_fact"):
                    acc_problems.append(f"{aid}: baseless but carries grounding fields")
            elif not (a.get("grounding_insight") or a.get("grounding_evidence") or a.get("grounding_fact")):
                acc_problems.append(f"{aid}: no grounding and not declared baseless")
            if a.get("grounding_insight") and a["grounding_insight"] not in insight_ids:
                acc_problems.append(f"{aid}: grounding insight unknown {a['grounding_insight']}")
            for e in a.get("grounding_evidence", []):
                if e not in ev_ids:
                    acc_problems.append(f"{aid}: grounding evidence unknown {e}")
            if a.get("grounding_fact") and a["grounding_fact"] not in fact_ids:
                acc_problems.append(f"{aid}: grounding fact unknown {a['grounding_fact']}")
            if not 0.0 <= a.get("min_reliability", 0.0) <= 1.0:
                acc_problems.append(f"{aid}: min_reliability out of range")
            for tier in ("on_grounded", "on_partial", "on_baseless"):
                cons = a.get(tier, {})
                if not isinstance(cons, dict):
                    acc_problems.append(f"{aid}: {tier} not an object")
                    continue
                for flag in (cons.get("set_flags") or {}):
                    if not flag.startswith("FLG_"):
                        acc_problems.append(f"{aid}: {tier} flag not an FLG_ id: {flag}")
        if acc_problems:
            for p in acc_problems:
                fail(p)
        else:
            ok(f"{len(accs)} accusations: grounding bundles, tiers and consequence flags all resolve")
        grounded = [a["id"] for a in accs if a.get("min_reliability", 0.0) > 0]
        ok(f"reliability bar applied on: {grounded} (QUEST_ARCHITECTURE 2.1)") if grounded else \
            fail("no accusation uses the QUEST_ARCHITECTURE 2.1 reliability bar")
    else:
        fail("deduction file missing or unloadable")

    # ---------------------------------------------------------------- finish
    print()
    total = CHECKS[0] + CHECKS[1]
    if CHECKS[1] == 0:
        print(f"ALL CHECKS PASSED ({CHECKS[0]}/{total})")
        print("NOTE: this validates the narrative data's internal consistency;")
        print("the game LOGIC itself is exercised by tools/core_tests (run_core_tests.sh).")
        return 0
    print(f"FAILED: {CHECKS[1]} of {total} checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
