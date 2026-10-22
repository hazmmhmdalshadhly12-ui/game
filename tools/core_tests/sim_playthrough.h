// THE LAST SIN: The Sin-Eater - M1
// sim_playthrough: a scripted bot that plays the full M1 slice through the
// REAL game-logic core (the same C++ compiled inside UE):
//   Day 1 (C1 complete): funeral -> boundary stone -> cottage -> dialogues
//     -> examination table -> deduction board -> insight -> sleep gate
//   Day 2 (C2 opening): mill discovery -> evidence -> board -> FLG_CASE_OPENED
// Also exercises the negative paths (gated sleep, unmet conditions, the
// examine-before-link rule, contradictions).

#pragma once

#include "TLSGameState.h"

namespace tls_test_sim
{

// Runs the full playthrough on the given (already data-loaded) game.
// Returns true when every scripted step succeeded (assertions inside use
// TLS_CHECK; this return is an additional hard gate).
bool RunFullPlaythrough(tls::Game& G, int& OutTotalInsights, int& OutCollectedEvidence);

// Runs the three alternative evidence paths to INS-REFUSAL (the chapter's
// big truth) on fresh game states - verifies the "3 paths" design rule.
bool RunThreePathVerification(tls::Game& G);

// Save/load round-trip: byte-stable mid-game save, then replaying from the
// loaded save reaches the exact same final state as an uninterrupted run
// (identical final save payload = zero drift, NPC_SIMULATION 10.2).
bool RunSaveLoadTest(tls::Game& G1, tls::Game& G2, tls::Game& G3);

} // namespace tls_test_sim
