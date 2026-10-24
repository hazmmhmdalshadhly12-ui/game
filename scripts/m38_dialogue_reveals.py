#!/usr/bin/env python3
"""M3.8: surgical dialogue edits (minimal diff, preserves the repo's inline
JSON style). Wires the dialogue -> case-fact testimony bridge into Gwen,
Coles and Crane, plus the two earned-confession branches and the
evidence-gated shadow admission."""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def edit(rel, pairs):
    path = os.path.join(ROOT, rel)
    with io.open(path, encoding="utf-8") as f:
        s = f.read()
    for old, new in pairs:
        if old not in s:
            raise SystemExit("ANCHOR NOT FOUND in %s:\n%s" % (rel, old))
        if s.count(old) != 1:
            raise SystemExit("ANCHOR NOT UNIQUE in %s (%d):\n%s" % (rel, s.count(old), old))
        s = s.replace(old, new)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(s)
    print("edited", rel)


# ---------------------------------------------------------------- Gwen (CHR-03)
edit("05_Narrative/dialogues/dlg_chr003_gwendolyn_c1.json", [
    # 1) the last-night tray account: her innocent version is hearable once
    #    EVD-GWEN-LASTNIGHT is held (H1 grants it right before this node);
    #    the testimony is a truth anchor - the board records it, it teaches
    #    nothing (canon: the poison truth lives in day-6 data).
    (
        '''      "text": "I poured it myself - his custom, four nights running, a small brandy with the laudanum the doctor allows old bones. But the bottle wasn't mine. Griffiths' boy carried it in with the coal, said it came by the doctor's instruction... and I remember thinking the boy's gloves were too fine for a miner's son.",
      "next": "NODE_HUB"''',
        '''      "text": "I poured it myself - his custom, four nights running, a small brandy with the laudanum the doctor allows old bones. But the bottle wasn't mine. Griffiths' boy carried it in with the coal, said it came by the doctor's instruction... and I remember thinking the boy's gloves were too fine for a miner's son.",
      "on_enter": { "reveal_facts": ["FACT-LAST-TRAY"] },
      "next": "NODE_HUB"''',
    ),
    # 2) the sworn '39 list: a hub choice at her registry trust threshold
    #    (60), only after the guinea-paper thread has been opened (H2).
    (
        '''        {
          "id": "H6",
          "tone": "formal",
          "text": "Nothing else. Thank you, Mrs Meredith.",
          "next": "NODE_END"
        }''',
        '''        {
          "id": "GU1",
          "tone": "gentle",
          "text": "Say it as testimony, Mrs Meredith - the seventeen names, and your own among them.",
          "conditions": { "flags": { "TOP_GUINEA": 1 }, "trust_min": 60 },
          "effects": { "trust_delta": 2, "set_flags": { "TOP_LIST_SWORN": 1 } },
          "next": "NODE_LIST_TOLD"
        },
        {
          "id": "H6",
          "tone": "formal",
          "text": "Nothing else. Thank you, Mrs Meredith.",
          "next": "NODE_END"
        }''',
    ),
    # 3) the sworn list node - the FACT-17-LIST testimony beat.
    (
        '''      "text": "You've a right to ask - you've his eyes and you ask like a man counting. There was a paper, October of '39. Seventeen names, seventeen guineas, one quiet night after the water went down. Mine's on it - Gwendolyn Meredith, and God help me, Ifor's schooling came out of it. The paper still exists. That's all I'll swear to you tonight.",
      "next": "NODE_HUB"
    },''',
        '''      "text": "You've a right to ask - you've his eyes and you ask like a man counting. There was a paper, October of '39. Seventeen names, seventeen guineas, one quiet night after the water went down. Mine's on it - Gwendolyn Meredith, and God help me, Ifor's schooling came out of it. The paper still exists. That's all I'll swear to you tonight.",
      "next": "NODE_HUB"
    },
    {
      "id": "NODE_LIST_TOLD",
      "speaker": "CHR-03",
      "text": "Seventeen of us signed the settlement paper of '39, cariad. Mine is not a clean name, whatever the parish thinks. Josiah kept the sure copy, and when he was past caring for it, I took it - for no good purpose and no bad one, only that a name on a paper should not outlive its asking. You may weigh that with the scales he kept, and let God do the arithmetic.",
      "on_enter": { "reveal_facts": ["FACT-17-LIST"] },
      "next": "NODE_HUB"
    },''',
    ),
])

# ---------------------------------------------------------------- Coles (CHR-13)
edit("05_Narrative/dialogues/dlg_chr013_coles_c1.json", [
    # 1) the fraud account: BH3 grants EVD-COLES-FRAUD before this node; the
    #    testimony requires exactly that evidence, so the line and the fact
    #    land together.
    (
        '''      "text": "Honest as a fox at a hen count, sir. I carried the poorhouse sacks to his floor this year past - light as widows' promises, every one. Missus Hawke counted the mouths, Nott counted the flour, and only one of them was counting true. I'd not swear it - I carried sacks, I didn't read the scale. But there it is.",
      "next": "NODE_HUB"''',
        '''      "text": "Honest as a fox at a hen count, sir. I carried the poorhouse sacks to his floor this year past - light as widows' promises, every one. Missus Hawke counted the mouths, Nott counted the flour, and only one of them was counting true. I'd not swear it - I carried sacks, I didn't read the scale. But there it is.",
      "on_enter": { "reveal_facts": ["FACT-NOTT-SIN"] },
      "next": "NODE_HUB"''',
    ),
    # 2) the ring confession: earned by kindness at his registry trust
    #    threshold (35) - the testimony's own gate.
    (
        '''        {
          "id": "BH4",
          "tone": "formal",
          "text": "Nothing else. Thank you, Mr Coles.",
          "next": "NODE_END"
        }''',
        '''        {
          "id": "BH5",
          "tone": "gentle",
          "text": "Whatever weight a man carries at three in the morning, Mr Coles - here is as good a place as any to set it down.",
          "conditions": { "trust_min": 35 },
          "effects": { "trust_delta": 2 },
          "next": "NODE_RING"
        },
        {
          "id": "BH4",
          "tone": "formal",
          "text": "Nothing else. Thank you, Mr Coles.",
          "next": "NODE_END"
        }''',
    ),
    # 3) the ring confession node - the FACT-COLES-RING testimony beat.
    (
        '''      "text": "Honest as a fox at a hen count, sir. I carried the poorhouse sacks to his floor this year past - light as widows' promises, every one. Missus Hawke counted the mouths, Nott counted the flour, and only one of them was counting true. I'd not swear it - I carried sacks, I didn't read the scale. But there it is.",
      "on_enter": { "reveal_facts": ["FACT-NOTT-SIN"] },
      "next": "NODE_HUB"
    },''',
        '''      "text": "Honest as a fox at a hen count, sir. I carried the poorhouse sacks to his floor this year past - light as widows' promises, every one. Missus Hawke counted the mouths, Nott counted the flour, and only one of them was counting true. I'd not swear it - I carried sacks, I didn't read the scale. But there it is.",
      "on_enter": { "reveal_facts": ["FACT-NOTT-SIN"] },
      "next": "NODE_HUB"
    },
    {
      "id": "NODE_RING",
      "speaker": "CHR-13",
      "text": "Since you ask kindly, and the ground keeps everything anyway... in '31 I lifted a ring off a hand I was burying. Small sin, they would say. It is not small at three in the morning, sir. The Hunger talk - folk need a name for the dark, and I gave them one so they would stop looking at the gate-keeper's hands.",
      "on_enter": { "reveal_facts": ["FACT-COLES-RING"] },
      "next": "NODE_END"
    },''',
    ),
])

# ---------------------------------------------------------------- Crane (CHR-04)
edit("05_Narrative/dialogues/dlg_chr004_crane_c1.json", [
    # the witnessed shadow: requires the physical evidence AND the pattern
    # insight - exactly the testimony's reveal gate. CH3 (the tower-hours
    # deflection) is untouched canon and keeps working without the prints.
    (
        '''        {
          "id": "CH4",
          "tone": "formal",
          "text": "Nothing further, Reverend.",
          "next": "NODE_END"
        }''',
        '''        {
          "id": "CH5",
          "tone": "pressing",
          "text": "[ Lay the wheel-race prints before him. ] You see everything from that tower, Rev. Crane. So tell me what moved in the mill yard that night.",
          "conditions": { "day_min": 2, "flags": { "TOP_TOWERSHADOW": 0 }, "has_evidence": ["EVD-FOOTPRINTS"], "knows_insight": ["INS-PATTERN"] },
          "effects": { "trust_delta": 1, "set_flags": { "TOP_TOWERSHADOW": 1 } },
          "next": "NODE_SHADOW_TOLD"
        },
        {
          "id": "CH4",
          "tone": "formal",
          "text": "Nothing further, Reverend.",
          "next": "NODE_END"
        }''',
    ),
    # the shadow admission node - the FACT-MILL-SHADOW testimony beat.
    (
        '''      "text": "You have your father's ledger-voice, sir, and I'll thank you to leave my tower out of your arithmetic. I keep the tower's hours... to myself. The tower and I keep the valley's hours between us. Is that all?",
      "next": "NODE_HUB"''',
        '''      "text": "You have your father's ledger-voice, sir, and I'll thank you to leave my tower out of your arithmetic. I keep the tower's hours... to myself. The tower and I keep the valley's hours between us. Is that all?",
      "next": "NODE_HUB"
    },
    {
      "id": "NODE_SHADOW_TOLD",
      "speaker": "CHR-04",
      "text": "You carry the prints from the wheel-race, so you will carry this too. I was on the tower that night - I go there to compose; the acoustics of guilt are honest from that height. A small shape crossed the yard below the wheel. Quick, bare-headed, gone toward the water. And when Pritchard asked his questions the next morning, I said nothing, because the shape I saw did not fit the sermon I had already written about this village.",
      "on_enter": { "reveal_facts": ["FACT-MILL-SHADOW"] },
      "next": "NODE_END"
    },''',
    ),
])

print("M3.8 dialogue reveal wiring complete (surgical)")
