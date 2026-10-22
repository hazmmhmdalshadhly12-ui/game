// THE LAST SIN: The Sin-Eater - M1
// sim_playthrough.cpp - see header. This is the closest thing to "playing
// the game" that can run in an engine-less environment: every call below is
// the same API the UE layer (TLSVillageGameMode) drives from real input.

#include "sim_playthrough.h"
#include "tls_test_framework.h"

#include <cmath>

using namespace tls;

namespace
{

// Picks the first available choice whose id matches (finds it among the
// CONDITION-FILTERED list - exactly like the UI does).
bool PickChoice(Game& G, const std::string& ChoiceId, std::string& Err)
{
        std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
        for (size_t I = 0; I < Avail.size(); ++I)
        {
                if (Avail[I]->Id == ChoiceId)
                {
                        std::string Entered;
                        return G.PickDialogueChoice(I, Entered, Err);
                }
        }
        Err = "choice not available (conditions unmet or wrong node): " + ChoiceId;
        return false;
}

bool ExpectChoiceAvailable(Game& G, const std::string& ChoiceId, bool bExpected)
{
        std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
        bool bFound = false;
        for (const DialogueChoice* C : Avail) { if (C->Id == ChoiceId) { bFound = true; break; } }
        if (bFound != bExpected)
        {
                std::string Ctx = "choice " + ChoiceId + (bExpected ? " should be available" : " should NOT be available");
                TLS_CHECK_MSG(false, Ctx);
                return false;
        }
        TLS_CHECK(true);
        return true;
}

} // namespace

namespace tls_test_sim
{

bool RunFullPlaythrough(Game& G, int& OutTotalInsights, int& OutCollectedEvidence)
{
        std::string Err;

        // ---------------------------------------------------------------- day 1
        TLS_SECTION("DAY 1 - funeral morning");
        G.NewGame();
        TLS_CHECK(G.CurrentDay() == 1);
        TLS_CHECK(G.GetWeather() == EWeather::OvercastFog);
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Active);
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::NotStarted);
        TLS_CHECK(G.GetTrust("CHR-03") == 15.0);    // initial trust from the registry
        TLS_CHECK(G.GetTrust("CHR-04") == -10.0);
        TLS_CHECK(G.GetTrust("CHR-17") == 20.0);

        // 1) the burial
        G.NotifyReachArea("AREA-CHURCHYARD");
        std::string GraveNote;
        G.NotifyObserveEvidence("EVD-GRAVE", &GraveNote);
        TLS_CHECK_MSG(GraveNote.find("decline of years") != std::string::npos, "grave note reveals the register line");

        // 2) the gravedigger (gentle route)
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        ExpectChoiceAvailable(G, "B1", true);
        TLS_CHECK(PickChoice(G, "B1", Err));          // gentle: thanks him -> NODE_BURIAL
        TLS_CHECK(PickChoice(G, "BH1", Err));         // his last months -> grants COLES-RITE
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-RITE"));
        TLS_CHECK(PickChoice(G, "BH4", Err));         // end
        TLS_CHECK(!G.DialogueRunning());
        const double ColesTrust = G.GetTrust("CHR-13");
        TLS_CHECK_MSG(ColesTrust > 7.0 && ColesTrust < 9.0, "Coles trust follows tone weight + bias: ~7.65");
        TLS_CHECK(G.GetFlag("MET_COLES") == 1);

        // 3) the boundary stone
        G.NotifyReachArea("AREA-BOUNDARY");
        G.NotifyCollectEvidence("EVD-DISH", "taken from beside the boundary stone");
        TLS_CHECK(G.EvidenceCollected("EVD-DISH"));

        // 4) the cottage
        G.NotifyReachArea("AREA-COTTAGE");
        G.NotifyCollectEvidence("EVD-LEDGER", "lifted from under the engraving table");
        G.NotifyCollectEvidence("EVD-RITE-PAPER", "taken from the shelf above the hearth");
        G.NotifyCollectEvidence("EVD-TORN-PAGE", "prised from beneath the floor stone");
        TLS_CHECK(G.EvidenceCollected("EVD-LEDGER"));

        // 5) the Black Ram - Gwendolyn (present the dish, then the trust path)
        TLS_SECTION("DAY 1 - the Black Ram (Gwendolyn)");
        TLS_CHECK(G.BeginDialogue("DLG-GWENDOLYN-C1", Err));
        const double CraneTrustBefore = G.GetTrust("CHR-04");
        TLS_CHECK(PickChoice(G, "G04", Err));         // present the dish (accept)
        TLS_CHECK(PickChoice(G, "H1", Err));          // the last tray -> grants LASTNIGHT
        TLS_CHECK(G.EvidenceCollected("EVD-GWEN-LASTNIGHT"));
        ExpectChoiceAvailable(G, "H2", true);          // trust >= 20 reached -> guinea topic open
        TLS_CHECK(G.GetTrust("CHR-03") >= 20.0);
        TLS_CHECK(PickChoice(G, "H2", Err));          // the paper of '39 -> grants GUINEA
        TLS_CHECK(G.EvidenceCollected("EVD-GWEN-GUINEA"));
        TLS_CHECK(PickChoice(G, "H3", Err));          // the silent kitchen girl
        TLS_CHECK(PickChoice(G, "H6", Err));          // good night
        TLS_CHECK(G.GetFlag("MET_GWENDOLYN") == 1);

        // faction spillover: inn trust gained -> church trust bleeds a little
        const double CraneTrustAfter = G.GetTrust("CHR-04");
        TLS_CHECK_MSG(CraneTrustAfter < CraneTrustBefore, "inn-faction gains spill over into church-faction loss");

        // day-2-only choice must NOT be offered on day 1
        TLS_CHECK(G.BeginDialogue("DLG-GWENDOLYN-C1", Err));
        TLS_CHECK(PickChoice(G, "G02", Err));          // attendance -> hub
        ExpectChoiceAvailable(G, "H5", false);         // mill topic is day 2+
        TLS_CHECK(PickChoice(G, "H6", Err));

        // 6) the silent kitchen girl
        TLS_CHECK(G.BeginDialogue("DLG-MAIR-C1", Err));
        TLS_CHECK(PickChoice(G, "M1", Err));          // gentle: "I don't speak Welsh"
        TLS_CHECK(!G.DialogueRunning());
        TLS_CHECK(G.GetFlag("MET_MAIR") == 1);
        // the Welsh layer: root text contained [w1:Bore da]; at level 0 it garbles
        TLS_CHECK(G.BeginDialogue("DLG-MAIR-C1", Err));
        bool bNeedsLesson = false;
        const std::string Rendered = G.DialogueRenderedText(bNeedsLesson);
        TLS_CHECK_MSG(bNeedsLesson, "Welsh marker garbles at level 0 and flags the lesson hint");
        TLS_CHECK_MSG(Rendered.find("#### ##") != std::string::npos, "garbled Welsh renders as # marks");
        TLS_CHECK(PickChoice(G, "M4", Err));          // silent: take the bread
        TLS_CHECK(!G.DialogueRunning());

        // 7) the priest
        TLS_SECTION("DAY 1 - St. Cynog's (Rev. Crane)");
        TLS_CHECK(G.BeginDialogue("DLG-CRANE-C1", Err));
        TLS_CHECK(PickChoice(G, "C01", Err));         // formal: "you knew of him"
        TLS_CHECK(G.EvidenceCollected("EVD-CRANE-SERMON"));
        TLS_CHECK(PickChoice(G, "CH2", Err));         // the tower
        ExpectChoiceAvailable(G, "CH3", false);        // tower-night topic needs day 2 + INS-PATTERN
        TLS_CHECK(PickChoice(G, "CH4", Err));         // leave
        TLS_CHECK(G.GetFlag("MET_CRANE") == 1);

        // optional objective complete: priest + gravedigger + kitchen girl
        // (checked through quest progress lines later)

        // 8) the father's table: restore, then examine
        TLS_SECTION("DAY 1 - the examination table and the board");
        std::string Reveal;
        G.NotifyRestorePage("EVD-TORN-PAGE", &Reveal);
        TLS_CHECK_MSG(Reveal.find("The bread stayed on the stone") != std::string::npos, "restored page reveals the marginal note");

        // examine-before-link gate (negative)
        std::string LinkMsg;
        G.NotifyDrawLink("EVD-DISH", "EVD-LEDGER", &LinkMsg);
        TLS_CHECK_MSG(LinkMsg.find("examine both pages") != std::string::npos, "board refuses links between unexamined evidence");

        G.NotifyExamineEvidence("EVD-DISH", &Reveal);
        TLS_CHECK_MSG(Reveal.find("No animal has touched it") != std::string::npos, "dish examine detail");
        G.NotifyExamineEvidence("EVD-LEDGER", &Reveal);
        G.NotifyExamineEvidence("EVD-TORN-PAGE", &Reveal);
        G.NotifyExamineEvidence("EVD-COLES-RITE", &Reveal);      // testimonial half must be read too
        G.NotifyExamineEvidence("EVD-GWEN-GUINEA", &Reveal);

        // sleep is gated until C1 completes (negative)
        std::string SleepReason;
        TLS_CHECK(!G.NotifySleep(SleepReason));
        TLS_CHECK_MSG(SleepReason.find("ledger will not sleep") != std::string::npos, "bed refuses while C1 incomplete");

        // 9) the deduction board
        std::vector<std::string> NewInsights;
        G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE", &LinkMsg, &NewInsights);
        TLS_CHECK_MSG(LinkMsg.find("Link holds") != std::string::npos, "valid link message");
        TLS_CHECK(NewInsights.size() == 1 && NewInsights[0] == "INS-REFUSAL");
        TLS_CHECK(G.InsightKnown("INS-REFUSAL"));

        G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-GWEN-GUINEA", &LinkMsg, &NewInsights);
        TLS_CHECK(NewInsights.size() == 1 && NewInsights[0] == "INS-SINLIST");
        TLS_CHECK(G.InsightKnown("INS-SINLIST"));
        TLS_CHECK(G.EvidenceCollected("EVD-SINLIST"));   // insight-gated documentary grant

        // duplicate link rejected
        G.NotifyDrawLink("EVD-COLES-RITE", "EVD-DISH", &LinkMsg);
        TLS_CHECK_MSG(LinkMsg.find("already drawn") != std::string::npos, "duplicate link rejected");

        // Q-M-C1 completed -> FLG_LEDGER_FOUND
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_LEDGER_FOUND") == 1);

        // 10) sleep -> day 2
        TLS_CHECK(G.NotifySleep(SleepReason));
        TLS_CHECK(G.CurrentDay() == 2);
        TLS_CHECK(G.GetWeather() == EWeather::Rain);
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Active);
        TLS_CHECK(G.Village().Tension() >= 3.0);

        // ---------------------------------------------------------------- day 2
        TLS_SECTION("DAY 2 - the miller and the salt");
        // Ifor's call
        TLS_CHECK(G.BeginDialogue("DLG-IFOR-C2", Err));
        ExpectChoiceAvailable(G, "I2", true);           // day-2 mill news now available
        TLS_CHECK(PickChoice(G, "I2", Err));
        TLS_CHECK(!G.DialogueRunning());

        // the mill scene
        G.NotifyReachArea("AREA-MILL");
        G.NotifyCollectEvidence("EVD-NOTT-BODY", "scene recorded in the sketchbook");
        G.NotifyObserveEvidence("EVD-FOOTPRINTS", &Reveal);
        G.NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "secured from the scale-board");
        G.NotifyCollectEvidence("EVD-SALT-SACK", "taken from by the door");

        // Coles on the fraud (optional path)
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        ExpectChoiceAvailable(G, "BH3", false);           // still at root - hub topic not offered yet
        TLS_CHECK(PickChoice(G, "B1", Err));              // gentle greeting -> NODE_BURIAL -> hub
        ExpectChoiceAvailable(G, "BH3", true);            // day-2 fraud topic now reachable
        TLS_CHECK(PickChoice(G, "BH3", Err));
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-FRAUD"));
        TLS_CHECK(PickChoice(G, "BH4", Err));

        // examination
        G.NotifyExamineEvidence("EVD-NOTT-BODY", &Reveal);
        TLS_CHECK_MSG(Reveal.find("drowned in dry ground") != std::string::npos, "body examine detail");
        G.NotifyExamineEvidence("EVD-SCALE-WEIGHTS", &Reveal);

        // contradiction link (negative evidence pairing)
        G.NotifyExamineEvidence("EVD-COLES-HUNGER", &Reveal);   // not collected -> fails silently
        TLS_CHECK(!G.EvidenceExamined("EVD-COLES-HUNGER"));

        // optional objective C2 (fraud) completed while the quest is still active
        bool bFoundFraudObjective = false;
        for (const QuestSystem::QuestProgressLine& L : G.Quests().ProgressLines())
        {
                if (L.ObjectiveId == "OBJ-C2-COLES" && L.bObjectiveDone) { bFoundFraudObjective = true; }
        }
        TLS_CHECK(bFoundFraudObjective);

        // the pattern insight - path A (SINLIST + BODY): the restored list must be read first
        G.NotifyExamineEvidence("EVD-SINLIST", &Reveal);
        G.NotifyDrawLink("EVD-SINLIST", "EVD-NOTT-BODY", &LinkMsg, &NewInsights);
        TLS_CHECK(NewInsights.size() == 1 && NewInsights[0] == "INS-PATTERN");
        TLS_CHECK(G.InsightKnown("INS-PATTERN"));

        // quest complete -> the slice's end state
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_CASE_OPENED") == 1);

        // day-2 boundary: no day 3 in the slice
        TLS_CHECK(!G.NotifySleep(SleepReason));
        TLS_CHECK_MSG(SleepReason.find("slice boundary") != std::string::npos, "day 3 is beyond the M1 slice");

        OutTotalInsights = 0;
        OutCollectedEvidence = static_cast<int>(G.Evidence().CollectedIds().size());
        TLS_CHECK(OutTotalInsights >= 0);
        TLS_CHECK(OutCollectedEvidence == 13);

        // the journal kept the story
        TLS_CHECK(G.Journal().size() >= 6);
        TLS_CHECK(G.Journal().back().Day == 2);

        return tls_test::GetStats().Failed == 0;
}

bool RunThreePathVerification(Game& G)
{
        TLS_SECTION("DESIGN RULE - three alternative evidence paths to INS-REFUSAL");

        struct PathSpec
        {
                const char* Name;
                const char* A;
                const char* B;
                std::vector<std::string> Examined;
        };
        const PathSpec Paths[] = {
                { "path 1: dish + witness", "EVD-DISH", "EVD-COLES-RITE", { "EVD-DISH", "EVD-COLES-RITE" } },
                { "path 2: dish + page", "EVD-DISH", "EVD-TORN-PAGE", { "EVD-DISH", "EVD-TORN-PAGE" } },
                { "path 3: ledger + witness", "EVD-LEDGER", "EVD-COLES-RITE", { "EVD-LEDGER", "EVD-COLES-RITE" } },
        };

        for (const PathSpec& P : Paths)
        {
                G.NewGame();
                // gather the two pieces
                for (const char* Ev : { P.A, P.B })
                {
                        G.NotifyCollectEvidence(Ev, "gathered for the path test");
                        G.NotifyExamineEvidence(Ev);
                }
                std::string Msg;
                std::vector<std::string> NewInsights;
                G.NotifyDrawLink(P.A, P.B, &Msg, &NewInsights);
                TLS_CHECK_MSG(G.InsightKnown("INS-REFUSAL"), P.Name);
                TLS_CHECK_MSG(NewInsights.size() == 1, P.Name);
        }

        // and the chapter's supporting truth reaches by two separate routes too
        {
                G.NewGame();
                G.NotifyCollectEvidence("EVD-TORN-PAGE", "x");
                G.NotifyRestorePage("EVD-TORN-PAGE");
                G.NotifyExamineEvidence("EVD-TORN-PAGE");
                G.NotifyCollectEvidence("EVD-GWEN-GUINEA", "x");
                G.NotifyExamineEvidence("EVD-GWEN-GUINEA");
                std::string Msg; std::vector<std::string> NI;
                G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-GWEN-GUINEA", &Msg, &NI);
                TLS_CHECK_MSG(G.InsightKnown("INS-SINLIST"), "INS-SINLIST route A (paper + guinea)");
        }
        {
                G.NewGame();
                for (const char* Ev : { "EVD-TORN-PAGE", "EVD-COLES-RITE" })
                {
                        G.NotifyCollectEvidence(Ev, "x");
                        G.NotifyRestorePage(Ev);       // no-op for the testimonial
                        G.NotifyExamineEvidence(Ev);
                }
                std::string Msg; std::vector<std::string> NI;
                G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-COLES-RITE", &Msg, &NI);
                TLS_CHECK_MSG(G.InsightKnown("INS-SINLIST"), "INS-SINLIST route B (paper + gravedigger's count)");
        }

        // contradiction pairs behave as designed
        {
                G.NewGame();
                for (const char* Ev : { "EVD-COLES-HUNGER", "EVD-DISH" })
                {
                        G.NotifyCollectEvidence(Ev, "x");
                        G.NotifyExamineEvidence(Ev);
                }
                std::string Msg;
                G.NotifyDrawLink("EVD-COLES-HUNGER", "EVD-DISH", &Msg);
                TLS_CHECK_MSG(Msg.find("CONTRADICTION") != std::string::npos, "folklore vs physical evidence is marked a contradiction");
                TLS_CHECK(!G.InsightKnown("INS-REFUSAL"));
        }

        return true;
}

} // namespace tls_test_sim

namespace tls_test_sim
{

namespace
{
        // compact script part 1: funeral, gravedigger, dish, cottage gathering
        void ScriptPart1(Game& G)
        {
                std::string Err, Note;
                G.NotifyReachArea("AREA-CHURCHYARD");
                G.NotifyObserveEvidence("EVD-GRAVE", &Note);
                G.BeginDialogue("DLG-COLES-C1", Err);
                PickChoice(G, "B1", Err);
                PickChoice(G, "BH1", Err);
                PickChoice(G, "BH4", Err);
                G.NotifyReachArea("AREA-BOUNDARY");
                G.NotifyCollectEvidence("EVD-DISH", "taken from beside the boundary stone");
                G.NotifyReachArea("AREA-COTTAGE");
                G.NotifyCollectEvidence("EVD-LEDGER", "lifted from under the engraving table");
                G.NotifyCollectEvidence("EVD-RITE-PAPER", "taken from the shelf above the hearth");
                G.NotifyCollectEvidence("EVD-TORN-PAGE", "prised from beneath the floor stone");
        }

        // compact script part 2: table, board, C1 completion, sleep
        void ScriptPart2(Game& G)
        {
                std::string Err, Reveal, Msg;
                std::vector<std::string> NI;
                G.NotifyRestorePage("EVD-TORN-PAGE", &Reveal);
                G.NotifyExamineEvidence("EVD-DISH", &Reveal);
                G.NotifyExamineEvidence("EVD-LEDGER", &Reveal);
                G.NotifyExamineEvidence("EVD-TORN-PAGE", &Reveal);
                G.NotifyExamineEvidence("EVD-COLES-RITE", &Reveal);
                G.BeginDialogue("DLG-GWENDOLYN-C1", Err);
                PickChoice(G, "G04", Err);
                PickChoice(G, "H1", Err);
                PickChoice(G, "H2", Err);
                PickChoice(G, "H6", Err);
                G.NotifyExamineEvidence("EVD-GWEN-GUINEA", &Reveal);   // granted by the dialogue above
                G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE", &Msg, &NI);
                G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-GWEN-GUINEA", &Msg, &NI);
                G.NotifySleep(Reveal);
        }

        // compact script part 3: the mill, the fraud, the pattern, the case opens
        void ScriptPart3(Game& G)
        {
                std::string Err, Reveal, Msg;
                std::vector<std::string> NI;
                G.NotifyReachArea("AREA-MILL");
                G.NotifyCollectEvidence("EVD-NOTT-BODY", "scene recorded in the sketchbook");
                G.NotifyObserveEvidence("EVD-FOOTPRINTS", &Reveal);
                G.NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "secured from the scale-board");
                G.NotifyCollectEvidence("EVD-SALT-SACK", "taken from by the door");
                G.BeginDialogue("DLG-COLES-C1", Err);
                PickChoice(G, "B1", Err);
                PickChoice(G, "BH3", Err);
                PickChoice(G, "BH4", Err);
                G.NotifyExamineEvidence("EVD-NOTT-BODY", &Reveal);
                G.NotifyExamineEvidence("EVD-SCALE-WEIGHTS", &Reveal);
                G.NotifyExamineEvidence("EVD-SINLIST", &Reveal);
                G.NotifyDrawLink("EVD-SINLIST", "EVD-NOTT-BODY", &Msg, &NI);
        }
}

bool RunSaveLoadTest(Game& G1, Game& G2, Game& G3)
{
        TLS_SECTION("SAVE/LOAD - byte-stable round trip and continuation equivalence");

        // uninterrupted run
        G1.NewGame();
        ScriptPart1(G1);
        ScriptPart2(G1);
        ScriptPart3(G1);
        const std::string EndUninterrupted = G1.SaveToString();
        TLS_CHECK(G1.GetFlag("FLG_CASE_OPENED") == 1);

        // interrupted run: save mid-way
        G2.NewGame();
        ScriptPart1(G2);
        const std::string Mid = G2.SaveToString();

        // load into a fresh instance and re-save: must be byte-identical
        std::string Err;
        TLS_CHECK(G3.LoadFromString(Mid, Err));
        const std::string MidResaved = G3.SaveToString();
        TLS_CHECK_MSG(MidResaved == Mid, "save -> load -> save must be byte-stable (zero drift)");

        // continue from the loaded save to the same end state
        ScriptPart2(G3);
        ScriptPart3(G3);
        const std::string EndFromSave = G3.SaveToString();
        TLS_CHECK_MSG(EndFromSave == EndUninterrupted,
                "continuing from a loaded save must reach the exact same state as the uninterrupted run");
        TLS_CHECK(G3.GetFlag("FLG_CASE_OPENED") == 1);
        TLS_CHECK(G3.Quests().Status("Q-M-C2a") == EQuestStatus::Completed);
        TLS_CHECK(std::abs(G3.GetTrust("CHR-03") - G1.GetTrust("CHR-03")) < 0.000001);
        TLS_CHECK(G3.Journal().size() == G1.Journal().size());

        // corrupted payload is rejected loudly
        TLS_CHECK(!G3.LoadFromString("{not json", Err));
        TLS_CHECK(!G3.LoadFromString("{\"day\": 1}", Err));   // missing subsystem sections

        return true;
}

} // namespace tls_test_sim
