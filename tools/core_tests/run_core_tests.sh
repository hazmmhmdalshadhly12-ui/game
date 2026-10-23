#!/usr/bin/env bash
# THE LAST SIN: The Sin-Eater - M1
# Builds and runs the standalone core-logic tests with g++.
# Usage: tools/core_tests/run_core_tests.sh   (from anywhere - resolves the repo root)
# Exit code 0 = all tests green. Runs in CI (ubuntu-latest) on every push.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"

CORE_DIR="$REPO_ROOT/03_Unreal/Source/TLS/Core"

echo "== TLS core-logic tests =="
echo "repo root : $REPO_ROOT"
echo "core dir  : $CORE_DIR"
echo "compiler  : $(g++ --version | head -1)"

mkdir -p "$BUILD_DIR"

BIN="$BUILD_DIR/tls_core_tests"
SRC="$SCRIPT_DIR/test_main.cpp $SCRIPT_DIR/test_rumors.cpp $SCRIPT_DIR/test_quests.cpp $SCRIPT_DIR/test_settings.cpp $SCRIPT_DIR/test_investigation.cpp $SCRIPT_DIR/sim_playthrough.cpp $CORE_DIR/TLSJson.cpp $CORE_DIR/TLSCoreTypes.cpp $CORE_DIR/TLSEvidence.cpp $CORE_DIR/TLSQuests.cpp $CORE_DIR/TLSVillageState.cpp $CORE_DIR/TLSDialogue.cpp $CORE_DIR/TLSRumors.cpp $CORE_DIR/TLSSettings.cpp $CORE_DIR/TLSGameState.cpp"

echo "== compiling (C++17, -Wall -Wextra) =="
g++ -std=c++17 -Wall -Wextra -Wno-unused-parameter -O1 -I "$CORE_DIR" -o "$BIN" $SRC
if [ $? -ne 0 ]; then
    echo "BUILD FAILED"
    exit 2
fi
echo "build ok -> $BIN"

echo "== running =="
( cd "$REPO_ROOT" && "$BIN" )
STATUS=$?

if [ $STATUS -eq 0 ]; then
    echo "RESULT: ALL CORE-LOGIC TESTS PASSED"
else
    echo "RESULT: CORE-LOGIC TESTS FAILED ($STATUS)"
fi
exit $STATUS
