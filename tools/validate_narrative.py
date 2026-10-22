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
        for q in quests["quests"]:
            if q["day_window_min"] > q["day_window_max"]:
                fail(f"{q['id']} inverted day window")
            optional = [o for o in q["objectives"] if o.get("optional")]
            if optional:
                ok(f"{q['id']}: {len(optional)} optional objective(s) never block completion")
            else:
                fail(f"{q['id']} has no optional objective (design: the slice teaches optional threads)")
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
        ok("quest task targets resolve against world/evidence/insights/dialogues")

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

    # ---------------------------------------------------------------- finish
    print()
    total = CHECKS[0] + CHECKS[1]
    if CHECKS[1] == 0:
        print(f"ALL CHECKS PASSED ({CHECKS[0]}/{total})")
        print("NOTE: this validates the narrative data's internal consistency;")
        print("the game LOGIC itself is exercised by tools/core_tests (418 checks).")
        return 0
    print(f"FAILED: {CHECKS[1]} of {total} checks failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
