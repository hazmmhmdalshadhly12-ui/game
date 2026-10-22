#!/usr/bin/env bash
# THE LAST SIN: The Sin-Eater - M2
# Builds and runs the reproducible core-simulation benchmark.
# Measures the algorithmic gossip-tick cost on the real 17-NPC village.
# The UE frame budget (<1.5 ms, NPC_SIMULATION 10) needs a live UE station.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CORE_DIR="$REPO_ROOT/03_Unreal/Source/TLS/Core"
BIN="/tmp/tls_bench_sim"
g++ -std=c++17 -O1 -I "$CORE_DIR" -o "$BIN" \
  "$SCRIPT_DIR/bench_sim.cpp" \
  "$CORE_DIR/TLSJson.cpp" "$CORE_DIR/TLSCoreTypes.cpp" "$CORE_DIR/TLSEvidence.cpp" \
  "$CORE_DIR/TLSQuests.cpp" "$CORE_DIR/TLSVillageState.cpp" "$CORE_DIR/TLSDialogue.cpp" \
  "$CORE_DIR/TLSRumors.cpp" "$CORE_DIR/TLSSettings.cpp" "$CORE_DIR/TLSGameState.cpp" || exit 2
( cd "$REPO_ROOT" && "$BIN" )
