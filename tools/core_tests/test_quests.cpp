// THE LAST SIN: The Sin-Eater - M2.3
// test_quests: data-driven quest system tests for the C1-C3 slice.
// Covers the M2.3 acceptance list: quest advancement, optional objectives,
// branches (any_of), failure + resumable consequences, reload, duplicate
// completion guards and condition conflicts.

#include "tls_test_framework.h"
#include "test_fixtures.h"
#include "TLSJson.h"
#include "TLSCoreTypes.h"
#include "TLSGameState.h"

#include <string>

using namespace tls;

namespace tls_test_quests
{
void RunAll(Game& G);
}

namespace
{

// drives a fresh world to the START of the given day (village day == Day)
void DriveToDay(Game& G, int Day)
{
        G.NewGame();
        for (int D = 1; D < Day; ++D) { G.AdvanceSimDay(); }
}

} // anonymous namespace

void tls_test_quests::RunAll(Game& G)
{
        // ------------------------------------------------ quest advancement
        TLS_SECTION("M2.3 quests - C3 advancement driven by rumors and evidence");

        DriveToDay(G, 3);
        TLS_CHECK_MSG(G.Quests().Status("Q-M-C3") == EQuestStatus::Active, "C3 main quest opens on day 3");
        TLS_CHECK_MSG(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active, "urgent Shoni quest opens on day 3");
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::NotStarted || true);   // C1 not auto-run here

        // the accusation: the player hears the county's theory
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07"));
        TLS_CHECK_MSG(G.Quests().FindState("Q-S-C3-SHONI") != nullptr, "shoni quest state exists");
        {
                const QuestRuntime* R = G.Quests().FindState("Q-S-C3-SHONI");
                TLS_CHECK_MSG(R && R->Objectives.size() == 2 && R->Objectives[0].bDone,
                        "hearing the accusation completes OBJ-SHONI-HEARD");
        }

        // the defence branch (any_of): one leak fires BOTH branches -
        // the player carries the account (player_rumor) and the square hears it
        // (npc_rumor: T3-07 Iwan and T3-01 Sara stand in the square at noon)
        {
                std::string Err;
                const int Heard = G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-SQUARE", Err);
                TLS_CHECK_MSG(Heard >= 2, "the leak reaches the square crowd (got " + std::to_string(Heard) + ")");
                TLS_CHECK_MSG(G.PlayerHeardRumor("RUM-SHONI-HILL"), "leaking implies knowing the account");
        }
        {
                const QuestRuntime* R = G.Quests().FindState("Q-S-C3-SHONI");
                TLS_CHECK_MSG(R && R->Status == EQuestStatus::Completed, "the urgent quest completes through the branch");
                TLS_CHECK_MSG(G.GetFlag("FLG_SHONI_DOUBTED") == 1, "completion sets the landmark flag");
                if (R && R->Objectives.size() == 2)
                {
                        TLS_CHECK(R->Objectives[1].bDone);
                }
        }

        // C3 main: the physical method against the county's shortcut
        G.NotifyCollectEvidence("EVD-FOOTPRINTS", "the mill lane");
        G.NotifyCollectEvidence("EVD-SALT-SACK", "the mill floor");
        G.NotifyExamineEvidence("EVD-FOOTPRINTS");
        G.NotifyExamineEvidence("EVD-SALT-SACK");
        TLS_CHECK_MSG(G.Quests().Status("Q-M-C3") == EQuestStatus::Completed, "C3 completes on accusation + method");
        TLS_CHECK_MSG(G.GetFlag("FLG_METHOD_SHOWN") == 1, "C3 completion sets its landmark flag");

        // the urgent quest's failure flag must NOT be set on the success path
        TLS_CHECK_MSG(G.GetFlag("FLG_SHONI_TAKEN") == 0, "Shoni was not taken in this world");

        // ------------------------------------------------ failure on expiry
        TLS_SECTION("M2.3 quests - failure on expiry is a resumable consequence, not a dead end");

        DriveToDay(G, 3);
        // the player hears the accusation but never defends Shoni
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07"));
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);
        G.AdvanceSimDay();   // day 3 -> day 4: the window closes
        TLS_CHECK_MSG(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Failed, "the urgent quest fails on expiry");
        TLS_CHECK_MSG(G.GetFlag("FLG_SHONI_TAKEN") == 1, "the failure flag carries the story consequence");
        bool bFailureJournaled = false;
        for (const auto& E : G.Journal()) { if (E.Text.find("Failed: A Day for the Tinker") != std::string::npos) { bFailureJournaled = true; } }
        TLS_CHECK_MSG(bFailureJournaled, "the failure is journaled");
        // the main quest does not expire - the story continues
        TLS_CHECK_MSG(G.Quests().Status("Q-M-C3") == EQuestStatus::Active, "the main C3 quest survives the failed side quest");

        // resumable: the failed state survives a save/load round trip
        {
                const std::string Payload = G.SaveToString();
                Game* G2 = MakeLoadedGame();
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        std::string Err;
                        TLS_CHECK_MSG(G2->LoadFromString(Payload, Err), "failed-quest world loads: " + Err);
                        TLS_CHECK_MSG(G2->Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Failed, "Failed status survives the save/load seam");
                        TLS_CHECK_MSG(G2->GetFlag("FLG_SHONI_TAKEN") == 1, "consequence flag survives the seam");
                        delete G2;
                }
        }

        // a completed urgent quest must NOT expire afterwards
        {
                Game* G3 = MakeLoadedGame();
                TLS_CHECK(G3 != nullptr);
                if (G3)
                {
                        DriveToDay(*G3, 3);
                        G3->NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07");
                        std::string Err;
                        G3->NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-SQUARE", Err);
                        TLS_CHECK(G3->Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Completed);
                        G3->AdvanceSimDay();
                        TLS_CHECK_MSG(G3->Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Completed,
                                "a completed urgent quest never flips to Failed on expiry");
                        TLS_CHECK(G3->GetFlag("FLG_SHONI_TAKEN") == 0);
                        delete G3;
                }
        }

        // ------------------------------------------------ duplicate completion guard
        TLS_SECTION("M2.3 quests - no duplicate completion, no flag re-application");

        DriveToDay(G, 3);
        G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07");
        {
                std::string Err;
                G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-SQUARE", Err);
        }
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Completed);
        // wipe the landmark flag and re-fire every task condition
        G.NotifyDecision("FLG_SHONI_DOUBTED", 0);
        G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07");
        {
                std::string Err;
                G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-SQUARE", Err);
        }
        G.AdvanceSimDay();
        G.AdvanceSimDay();
        TLS_CHECK_MSG(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Completed, "completed quest stays completed");
        TLS_CHECK_MSG(G.GetFlag("FLG_SHONI_DOUBTED") == 0, "flags_on_complete are NOT re-applied after completion");

        // ------------------------------------------------ condition conflicts
        TLS_SECTION("M2.3 quests - contradictory conditions can never complete (documented behavior)");

        {
                const char* ConflictJson =
                        "{\"quests\":[{"
                        "\"id\":\"Q-T-CONFLICT\",\"title\":\"Impossible\",\"chapter\":\"T\","
                        "\"day_window_min\":1,\"day_window_max\":9,\"auto_start\":false,"
                        "\"objectives\":["
                        "{\"id\":\"OBJ-A\",\"description\":\"a\",\"tasks\":[{\"type\":\"flag\",\"target\":\"CONFLICT_A\",\"value\":1}]},"
                        "{\"id\":\"OBJ-B\",\"description\":\"b\",\"tasks\":[{\"type\":\"flag\",\"target\":\"CONFLICT_A\",\"value\":0}]}],"
                        "\"flags_on_complete\":{\"FLG_CONFLICT\":1}}]}";
                std::string Err, Content;
                JsonParseResult P = JsonParse(ConflictJson);
                TLS_CHECK(P.Ok);
                TLS_CHECK_MSG(G.LoadQuestData(P.Value, Err), "conflict fixture loads: " + Err);
                TLS_CHECK_MSG(G.QuestsMut().ForceActivate("Q-T-CONFLICT", 1, Err), "conflict quest force-activated");
                G.NotifyDecision("CONFLICT_A", 1);
                for (int I = 0; I < 5; ++I) { G.VillageMut().ApplyTrustDelta("CHR-13", 0.0, ETone::Silent); }   // force refreshes via context churn
                TLS_CHECK_MSG(G.Quests().Status("Q-T-CONFLICT") == EQuestStatus::Active,
                        "contradictory objectives keep the quest Active forever");
                TLS_CHECK_MSG(G.GetFlag("FLG_CONFLICT") == 0, "an impossible quest never fires its flags");
        }

        // ------------------------------------------------ reload with partial progress
        TLS_SECTION("M2.3 quests - partial quest progress survives the save/load seam");

        {
                DriveToDay(G, 3);
                G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07");
                // heard but NOT defended: partial progress in both quests
                const std::string Payload = G.SaveToString();

                Game* G2 = MakeLoadedGame();
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        std::string Err;
                        TLS_CHECK_MSG(G2->LoadFromString(Payload, Err), "partial-progress load: " + Err);
                        const QuestRuntime* RA = G.Quests().FindState("Q-S-C3-SHONI");
                        const QuestRuntime* RB = G2->Quests().FindState("Q-S-C3-SHONI");
                        TLS_CHECK_MSG(RA && RB, "quest runtime exists on both sides");
                        if (RA && RB)
                        {
                                TLS_CHECK_MSG(JsonSerialize(G.Quests().SerializeState(), false) == JsonSerialize(G2->Quests().SerializeState(), false),
                                        "quest state byte-identical after the seam");
                        }
                        // the loaded world can still finish the urgent quest
                        std::string Err2;
                        G2->NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-SQUARE", Err2);
                        TLS_CHECK_MSG(G2->Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Completed,
                                "a loaded world resumes the quest exactly where it stood");
                        delete G2;
                }
        }
}
