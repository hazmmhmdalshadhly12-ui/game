// THE LAST SIN: The Sin-Eater - M2
// test_fixtures: shared game-factory declaration for the test files.

#pragma once

namespace tls
{
class Game;
}

// Builds a Game with every 05_Narrative data file loaded (evidence, quests,
// sim, rumors, dialogues). Defined in test_main.cpp; the data-loading checks
// run through the shared test framework.
tls::Game* MakeLoadedGame();
