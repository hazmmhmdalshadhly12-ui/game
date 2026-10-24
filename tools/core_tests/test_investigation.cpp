// THE LAST SIN: The Sin-Eater - M3.1
// test_investigation: the first complete investigation loop, played end to end
// through the REAL game-logic core using ONLY the existing systems and the
// story data already in the repo (no invented events, no simplified copies):
//
//   day 1 (C1): new game -> funeral -> gravedigger testimony -> the dish ->
//     the cottage -> the Black Ram -> the table -> the board -> C1 complete
//   day 2 (C2): the mill scene -> witness registration -> fraud testimony ->
//     the pattern -> case opened -> SAVE SEAM
//   day 3 (C3, via the pure sim advance): accusation rumor heard -> physical
//     method -> the anonymous leak closes the urgent any_of branch
//
// Plus the M3.1 regression battery: repeated interactions, unknown ids,
// corrupt/unsupported saves with ATOMIC refusal (state must not change
// partially), quest expiry failure + any_of honesty, rumor spread limits and
// witness knowledge, and same-seed determinism of the whole loop.

#include "tls_test_framework.h"
#include "test_fixtures.h"

#include "TLSGameState.h"

#include <string>
#include <vector>

using namespace tls;

namespace tls_test_investigation
{

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

bool ObjectiveDone(Game& G, const std::string& ObjectiveId)
{
        for (const QuestSystem::QuestProgressLine& L : G.Quests().ProgressLines())
        {
                if (L.ObjectiveId == ObjectiveId) { return L.bObjectiveDone; }
        }
        return false;
}

} // anonymous namespace

// ---------------------------------------------------------------- the loop

void RunInvestigationLoop(Game& G)
{
        std::string Err, Note, Reveal, Msg, SleepReason;
        std::vector<std::string> NI;

        // ------------------------------------------------ day 1 (C1)
        TLS_SECTION("M3.1 loop - day 1: new game, the funeral, the dish, the board");

        // new game + player-state init
        G.NewGame();
        TLS_CHECK(G.CurrentDay() == 1);
        TLS_CHECK(G.GetWeather() == EWeather::OvercastFog);
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Active);
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::NotStarted);
        TLS_CHECK(G.Quests().Status("Q-M-C3") == EQuestStatus::NotStarted);
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::NotStarted);
        TLS_CHECK(G.GetTrust("CHR-03") == 15.0);
        TLS_CHECK(G.GetTrust("CHR-04") == -10.0);
        TLS_CHECK(G.GetTrust("CHR-17") == 20.0);

        // rumor layer init: day-1 seeds present, later-day rumors dark
        TLS_CHECK(G.Rumors().NpcKnows("T3-06", "RUM-HUNGER-RETURNS"));
        TLS_CHECK(G.Rumors().NpcKnows("T3-03", "RUM-HUNGER-RETURNS"));
        TLS_CHECK(G.Rumors().KnowerCount("RUM-NOTT-SALT") == 0);
        TLS_CHECK(G.Rumors().KnowerCount("RUM-SHONI-SUSPECT") == 0);
        TLS_CHECK(G.Rumors().KnowerCount("RUM-SHONI-HILL") == 0);

        // village gossip obeys the system rules (zones, reticence, daily cap)
        {
                bool bZonesClean = true, bMairSpoke = false;
                int NewKnowers = 0;
                for (int Hour : { 9, 12, 18 })
                {
                        const RumorSystem::TickResult Res = G.TickVillageGossip(1, Hour);
                        NewKnowers += Res.NewKnowersToday;
                        for (const RumorTransmission& T : Res.NewTransmissions)
                        {
                                if (!G.Rumors().IsGossipZone(T.Zone)) { bZonesClean = false; }
                                if (T.FromNpc == "CHR-06") { bMairSpoke = true; }   // reticence 0.9
                        }
                }
                TLS_CHECK(bZonesClean);
                TLS_CHECK_MSG(!bMairSpoke, "Mair (reticence 0.9) never carries gossip");
                TLS_CHECK_MSG(NewKnowers <= 5, "day-1 spread stays inside the 30% daily cap (17 NPCs)");
        }

        // evidence through valid interaction paths
        G.NotifyReachArea("AREA-CHURCHYARD");
        G.NotifyObserveEvidence("EVD-GRAVE", &Note);
        TLS_CHECK_MSG(Note.find("decline of years") != std::string::npos, "grave note reveals the register line");

        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        TLS_CHECK(PickChoice(G, "B1", Err));
        TLS_CHECK(PickChoice(G, "BH1", Err));                       // grants the rite testimony
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-RITE"));
        TLS_CHECK(PickChoice(G, "BH4", Err));
        TLS_CHECK(G.GetFlag("MET_COLES") == 1);

        // quest updates only when their actual conditions verify
        TLS_CHECK_MSG(G.Quests().Status("Q-M-C1") == EQuestStatus::Active,
                "the funeral alone does not complete C1");
        TLS_CHECK(!ObjectiveDone(G, "OBJ-C1-DISH"));
        TLS_CHECK(!ObjectiveDone(G, "OBJ-C1-BOARD"));

        G.NotifyReachArea("AREA-BOUNDARY");
        G.NotifyCollectEvidence("EVD-DISH", "taken from beside the boundary stone");
        TLS_CHECK(G.EvidenceCollected("EVD-DISH"));
        G.NotifyReachArea("AREA-COTTAGE");
        G.NotifyCollectEvidence("EVD-LEDGER", "lifted from under the engraving table");
        G.NotifyCollectEvidence("EVD-RITE-PAPER", "taken from the shelf above the hearth");
        G.NotifyCollectEvidence("EVD-TORN-PAGE", "prised from beneath the floor stone");

        // the Black Ram - Gwendolyn (MET_GWENDOLYN is a required C1 task)
        TLS_CHECK(G.BeginDialogue("DLG-GWENDOLYN-C1", Err));
        TLS_CHECK(PickChoice(G, "G04", Err));                       // present the dish
        TLS_CHECK(PickChoice(G, "H1", Err));                        // the last tray
        TLS_CHECK(G.EvidenceCollected("EVD-GWEN-LASTNIGHT"));
        TLS_CHECK(PickChoice(G, "H2", Err));                        // the paper of '39
        TLS_CHECK(G.EvidenceCollected("EVD-GWEN-GUINEA"));
        TLS_CHECK(PickChoice(G, "H3", Err));
        TLS_CHECK(PickChoice(G, "H6", Err));
        TLS_CHECK(G.GetFlag("MET_GWENDOLYN") == 1);

        // the player hears the day-1 rumor (once - no duplicate record)
        {
                const size_t JBefore = G.Journal().size();
                TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06"));
                TLS_CHECK(G.PlayerHeardRumor("RUM-HUNGER-RETURNS"));
                TLS_CHECK(G.Journal().size() == JBefore + 1);
                TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06"));
                TLS_CHECK(G.Journal().size() == JBefore + 1);
        }

        // the father's table: restore, then examine
        G.NotifyRestorePage("EVD-TORN-PAGE", &Reveal);
        TLS_CHECK_MSG(Reveal.find("The bread stayed on the stone") != std::string::npos,
                "restored page reveals the marginal note");
        G.NotifyExamineEvidence("EVD-DISH", &Reveal);
        G.NotifyExamineEvidence("EVD-LEDGER", &Reveal);
        G.NotifyExamineEvidence("EVD-TORN-PAGE", &Reveal);
        G.NotifyExamineEvidence("EVD-COLES-RITE", &Reveal);
        G.NotifyExamineEvidence("EVD-GWEN-GUINEA", &Reveal);

        // the sleep gate refuses while C1 is open
        TLS_CHECK(!G.NotifySleep(SleepReason));
        TLS_CHECK_MSG(SleepReason.find("ledger will not sleep") != std::string::npos,
                "bed refuses while C1 incomplete");

        // the ledger board: the chapter's truths, only now
        G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE", &Msg, &NI);
        TLS_CHECK(NI.size() == 1 && NI[0] == "INS-REFUSAL");
        G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-GWEN-GUINEA", &Msg, &NI);
        TLS_CHECK(NI.size() == 1 && NI[0] == "INS-SINLIST");
        TLS_CHECK(G.EvidenceCollected("EVD-SINLIST"));              // insight-gated grant
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_LEDGER_FOUND") == 1);

        // rumor tool: public denial - holders dented, reputation rewarded
        {
                int Holders = 0;
                for (const std::string& R : G.Rumors().ActiveRumorIds())
                {
                        Holders += G.Rumors().KnowerCount(R);
                }
                const double RepBefore = G.Village().Reputation();
                TLS_CHECK(G.NotifyPlayerRumorDenial() == Holders);
                TLS_CHECK_MSG(G.Village().Reputation() == RepBefore + 2.0,
                        "the village rewards a public stand");
        }

        // sleep -> day 2
        TLS_CHECK(G.NotifySleep(SleepReason));
        TLS_CHECK(G.CurrentDay() == 2);
        TLS_CHECK(G.GetWeather() == EWeather::Rain);
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Active);
        TLS_CHECK(G.Village().Tension() >= 3.0);
        TLS_CHECK_MSG(G.Rumors().NpcKnows("T3-02", "RUM-NOTT-SALT"),
                "the mill discovery enters the village rumor layer on day 2");
        TLS_CHECK(!G.PlayerHeardRumor("RUM-NOTT-SALT"));

        // ------------------------------------------------ day 2 (C2)
        TLS_SECTION("M3.1 loop - day 2: the mill, the witness, the case opens");

        TLS_CHECK(G.BeginDialogue("DLG-IFOR-C2", Err));
        TLS_CHECK(PickChoice(G, "I2", Err));                        // day-2 mill news
        TLS_CHECK(!G.DialogueRunning());

        G.NotifyReachArea("AREA-MILL");
        G.NotifyCollectEvidence("EVD-NOTT-BODY", "scene recorded in the sketchbook");
        G.NotifyObserveEvidence("EVD-FOOTPRINTS", &Reveal);
        G.NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "secured from the scale-board");
        G.NotifyCollectEvidence("EVD-SALT-SACK", "taken from by the door");

        // witness registration: the square hears the finder's alarm - direct
        // testimony, and the same (event, witness) pair never records twice
        {
                std::string WErr;
                const int Before = G.Rumors().KnowerCount("RUM-NOTT-SALT");
                TLS_CHECK(G.NotifyWitnessEvent("RUM-NOTT-SALT", 2, 9, "AREA-SQUARE", { "T3-05" }, WErr));
                TLS_CHECK(G.Rumors().KnowerCount("RUM-NOTT-SALT") == Before + 1);
                TLS_CHECK(G.NotifyWitnessEvent("RUM-NOTT-SALT", 2, 9, "AREA-SQUARE", { "T3-05" }, WErr));
                TLS_CHECK_MSG(G.Rumors().KnowerCount("RUM-NOTT-SALT") == Before + 1,
                        "a repeated witness event never double-records");
                const RumorKnowledge* KW = G.Rumors().NpcKnowledge("T3-05", "RUM-NOTT-SALT");
                TLS_CHECK_MSG(KW != nullptr && KW->Kind == ETestimonyKind::Direct,
                        "a registered witness holds direct testimony");
        }

        // Coles on the fraud (the optional C2 objective)
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        TLS_CHECK(PickChoice(G, "B1", Err));
        TLS_CHECK(PickChoice(G, "BH3", Err));
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-FRAUD"));
        TLS_CHECK(PickChoice(G, "BH4", Err));
        TLS_CHECK(ObjectiveDone(G, "OBJ-C2-COLES"));

        // examination + the pattern insight
        G.NotifyExamineEvidence("EVD-NOTT-BODY", &Reveal);
        TLS_CHECK_MSG(Reveal.find("drowned in dry ground") != std::string::npos, "body examine detail");
        G.NotifyExamineEvidence("EVD-SCALE-WEIGHTS", &Reveal);
        G.NotifyExamineEvidence("EVD-SINLIST", &Reveal);
        G.NotifyDrawLink("EVD-SINLIST", "EVD-NOTT-BODY", &Msg, &NI);
        TLS_CHECK(NI.size() == 1 && NI[0] == "INS-PATTERN");
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_CASE_OPENED") == 1);

        // the player hears the mill news
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-NOTT-SALT", "T3-02"));
        TLS_CHECK(G.PlayerHeardRumor("RUM-NOTT-SALT"));

        // ------------------------------------------------ the save seam
        TLS_SECTION("M3.1 loop - the save/load seam: nothing of the loop is lost");

        const std::string S2 = G.SaveToString();
        TLS_CHECK(S2.find("\"save_version\":3") != std::string::npos);
        TLS_CHECK(S2.find("\"sim_rng\":") != std::string::npos);
        TLS_CHECK(static_cast<int>(G.Evidence().CollectedIds().size()) == 12);
        const size_t JournalAtS2 = G.Journal().size();

        {
                Game* GL = MakeLoadedGame();
                TLS_CHECK(GL != nullptr);
                if (GL)
                {
                        std::string LErr;
                        TLS_CHECK_MSG(GL->LoadFromString(S2, LErr), "seam load: " + LErr);
                        // quest/evidence/rumor state survives the seam exactly
                        TLS_CHECK(GL->Quests().Status("Q-M-C1") == EQuestStatus::Completed);
                        TLS_CHECK(GL->Quests().Status("Q-M-C2a") == EQuestStatus::Completed);
                        TLS_CHECK(GL->Quests().Status("Q-M-C3") == EQuestStatus::NotStarted);
                        TLS_CHECK(GL->GetFlag("FLG_LEDGER_FOUND") == 1);
                        TLS_CHECK(GL->GetFlag("FLG_CASE_OPENED") == 1);
                        TLS_CHECK(static_cast<int>(GL->Evidence().CollectedIds().size()) == 12);
                        TLS_CHECK(GL->EvidenceExamined("EVD-NOTT-BODY"));
                        TLS_CHECK(GL->InsightKnown("INS-PATTERN"));
                        TLS_CHECK(GL->PlayerHeardRumor("RUM-NOTT-SALT"));
                        TLS_CHECK(GL->Rumors().NpcKnows("T3-05", "RUM-NOTT-SALT"));
                        TLS_CHECK(GL->Journal().size() == JournalAtS2);
                        TLS_CHECK(GL->SaveToString() == S2);            // byte-stable round trip
                        delete GL;
                }
        }

        // the same session continues (load back into the running game)
        TLS_CHECK(G.LoadFromString(S2, Err));
        TLS_CHECK(G.CurrentDay() == 2);

        // ------------------------------------------------ day 3 (C3)
        TLS_SECTION("M3.1 loop - day 3: the accusation, the method, the leak");

        G.AdvanceSimDay();                                          // pure sim advance into C3
        TLS_CHECK(G.CurrentDay() == 3);
        TLS_CHECK(G.Quests().Status("Q-M-C3") == EQuestStatus::Active);
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);
        TLS_CHECK(G.Rumors().NpcKnows("T3-07", "RUM-SHONI-SUSPECT"));
        TLS_CHECK(!G.PlayerHeardRumor("RUM-SHONI-SUSPECT"));

        // the alibi any_of must NOT be satisfied by the accusation rumor
        TLS_CHECK(!ObjectiveDone(G, "OBJ-SHONI-ALIBI"));
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);

        // the player hears the county's theory
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07"));
        TLS_CHECK(G.PlayerHeardRumor("RUM-SHONI-SUSPECT"));
        TLS_CHECK(ObjectiveDone(G, "OBJ-C3-ACCUSATION"));
        TLS_CHECK(ObjectiveDone(G, "OBJ-SHONI-HEARD"));
        TLS_CHECK_MSG(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active,
                "hearing the accusation does not complete the urgent quest - the alibi is still owed");

        // the physical method (footprints collected on the day-3 visit)
        G.NotifyCollectEvidence("EVD-FOOTPRINTS", "recorded from the wheel-race mud");
        G.NotifyExamineEvidence("EVD-FOOTPRINTS", &Reveal);
        G.NotifyExamineEvidence("EVD-SALT-SACK", &Reveal);
        TLS_CHECK(G.Quests().Status("Q-M-C3") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_METHOD_SHOWN") == 1);

        // the anonymous leak puts the alibi into circulation (any_of branch a)
        {
                int Heard = 0;
                for (const char* Zone : { "AREA-SQUARE", "AREA-INN", "AREA-CHURCH", "AREA-CHURCHYARD" })
                {
                        Heard = G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", Zone, Err);
                        if (Heard > 0) { break; }
                }
                TLS_CHECK_MSG(Heard > 0, "the leak reaches somebody in a gossip zone at noon");
                TLS_CHECK(G.PlayerHeardRumor("RUM-SHONI-HILL"));    // the player knows what they spread
                bool bPlayerInChain = false;
                for (const RumorTransmission& T : G.Rumors().TransmissionLog())
                {
                        if (T.RumorId == "RUM-SHONI-HILL" && T.FromNpc == "PLAYER") { bPlayerInChain = true; }
                }
                TLS_CHECK(bPlayerInChain);
        }

        // the leak's word travels on through the gossip zones (deterministic)
        for (int Hour = 13; Hour <= 21; ++Hour)
        {
                const RumorSystem::TickResult Res = G.TickVillageGossip(3, Hour);
                for (const RumorTransmission& T : Res.NewTransmissions)
                {
                        TLS_CHECK_MSG(G.Rumors().IsGossipZone(T.Zone), "day-3 transmissions stay in gossip zones");
                }
        }
        TLS_CHECK(G.Rumors().KnowerCount("RUM-SHONI-HILL") >= 2);   // player + at least one villager
        for (const std::string& Knower : G.Rumors().NpcsKnowing("RUM-SHONI-HILL"))
        {
                if (Knower == "PLAYER") { continue; }
                const std::vector<RumorTransmission> Chain =
                        G.Rumors().TraceProvenance("RUM-SHONI-HILL", Knower);
                TLS_CHECK_MSG(!Chain.empty(), "every leaked knower has a provenance chain back to the player");
        }

        // the urgent quest closes through the leak branch
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_SHONI_DOUBTED") == 1);
        TLS_CHECK(G.GetFlag("FLG_SHONI_TAKEN") == 0);

        // the loop's final state is richer than the seam's and saveable
        TLS_CHECK(G.Journal().size() > JournalAtS2);
        TLS_CHECK(static_cast<int>(G.Evidence().CollectedIds().size()) == 13);
        const std::string S3 = G.SaveToString();
        TLS_CHECK(!S3.empty());
}

// ---------------------------------------------------------------- regressions

void TestRepeatedInteractions(Game& G)
{
        TLS_SECTION("M3.1 regression - repeated interactions never double-record");

        G.NewGame();

        // collecting the same evidence twice keeps one custody entry
        G.NotifyCollectEvidence("EVD-DISH", "first take");
        G.NotifyCollectEvidence("EVD-DISH", "second take - must not record");
        const EvidenceRuntime* R = G.Evidence().State("EVD-DISH");
        TLS_CHECK(R != nullptr);
        TLS_CHECK_MSG(R->ChainOfCustody.size() == 1, "one custody entry per evidence");
        TLS_CHECK(R->DayCollected == 1);

        // observing twice is idempotent
        G.NotifyObserveEvidence("EVD-GRAVE");
        G.NotifyObserveEvidence("EVD-GRAVE");
        TLS_CHECK(G.EvidenceObserved("EVD-GRAVE"));

        // the board link records once - both orders of the duplicate refused
        G.NotifyExamineEvidence("EVD-DISH");
        G.NotifyCollectEvidence("EVD-COLES-RITE", "witness account");
        G.NotifyExamineEvidence("EVD-COLES-RITE");
        std::string Msg;
        std::vector<std::string> NI;
        G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE", &Msg, &NI);
        TLS_CHECK(G.InsightKnown("INS-REFUSAL"));
        G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE", &Msg);
        TLS_CHECK_MSG(Msg.find("already drawn") != std::string::npos, "same-order duplicate link refused");
        G.NotifyDrawLink("EVD-COLES-RITE", "EVD-DISH", &Msg);
        TLS_CHECK_MSG(Msg.find("already drawn") != std::string::npos, "reverse-order duplicate link refused");

        // witness events and player-heard records are idempotent
        std::string WErr;
        const int Base = G.Rumors().KnowerCount("RUM-HUNGER-RETURNS");
        TLS_CHECK(G.NotifyWitnessEvent("RUM-HUNGER-RETURNS", 1, 10, "AREA-CHURCHYARD", { "T3-08" }, WErr));
        TLS_CHECK(G.Rumors().KnowerCount("RUM-HUNGER-RETURNS") == Base + 1);
        TLS_CHECK(G.NotifyWitnessEvent("RUM-HUNGER-RETURNS", 1, 10, "AREA-CHURCHYARD", { "T3-08" }, WErr));
        TLS_CHECK(G.Rumors().KnowerCount("RUM-HUNGER-RETURNS") == Base + 1);

        const size_t JB = G.Journal().size();
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06"));
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06"));
        TLS_CHECK(G.Journal().size() == JB + 1);
}

void TestUnknownIds(Game& G)
{
        TLS_SECTION("M3.1 regression - unknown ids are refused, never fabricated");

        G.NewGame();

        G.NotifyCollectEvidence("EVD-GHOST", "x");
        TLS_CHECK(!G.EvidenceCollected("EVD-GHOST"));
        G.NotifyExamineEvidence("EVD-GHOST");
        TLS_CHECK(!G.EvidenceExamined("EVD-GHOST"));
        G.NotifyRestorePage("EVD-GHOST");
        TLS_CHECK(!G.EvidenceRestored("EVD-GHOST"));
        TLS_CHECK(G.Evidence().FindDef("EVD-GHOST") == nullptr);
        TLS_CHECK(G.Evidence().State("EVD-GHOST") == nullptr);

        std::string Msg;
        G.NotifyDrawLink("EVD-GHOST", "EVD-DISH", &Msg);
        TLS_CHECK(!G.InsightKnown("INS-REFUSAL"));

        std::string Err;
        TLS_CHECK(!G.BeginDialogue("DLG-GHOST", Err));
        TLS_CHECK(!Err.empty());
        TLS_CHECK(!G.DialogueRunning());

        TLS_CHECK(G.Quests().Status("Q-GHOST") == EQuestStatus::NotStarted);
        TLS_CHECK(!G.QuestsMut().ForceActivate("Q-GHOST", 1, Err));
        TLS_CHECK(Err.find("unknown quest") != std::string::npos);

        TLS_CHECK(!G.NotifyWitnessEvent("RUM-GHOST", 1, 9, "AREA-SQUARE", { "T3-06" }, Err));
        TLS_CHECK(Err.find("unknown rumor") != std::string::npos);
        TLS_CHECK(G.NotifyPlayerLeakRumor("RUM-GHOST", "AREA-SQUARE", Err) == -1);
        TLS_CHECK(!G.NotifyPlayerHeardRumor("RUM-GHOST", "T3-06"));
        TLS_CHECK(G.Rumors().FindDef("RUM-GHOST") == nullptr);
        TLS_CHECK(G.Rumors().NpcKnowledge("T3-06", "RUM-GHOST") == nullptr);

        TLS_CHECK(G.GetTrust("CHR-GHOST") == 0.0);
        TLS_CHECK(G.Village().NpcZoneAt("CHR-GHOST", 12).empty());
        TLS_CHECK(!G.NpcKnowsRumor("CHR-GHOST", "RUM-HUNGER-RETURNS"));
        TLS_CHECK(!G.InsightKnown("INS-GHOST"));
}

void TestAtomicLoadRefusal(Game& G)
{
        TLS_SECTION("M3.1 regression - a refused save load leaves the session byte-identical");

        // a distinctive running session (day 1, evidence in hand, rumors flowing)
        G.NewGame();
        G.NotifyCollectEvidence("EVD-DISH", "session evidence");
        G.NotifyCollectEvidence("EVD-LEDGER", "session evidence");
        G.TickVillageGossip(1, 8);
        G.TickVillageGossip(1, 9);
        G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06");
        const std::string Session = G.SaveToString();

        // a DIFFERENT world (day 2, rain, tension 3) whose village section would
        // visibly change the running session if a load were not atomic
        Game* GAlt = MakeLoadedGame();
        TLS_CHECK(GAlt != nullptr);
        if (!GAlt) { return; }
        GAlt->NewGame();
        GAlt->AdvanceSimDay();
        const std::string Alt = GAlt->SaveToString();
        TLS_CHECK(Alt != Session);
        delete GAlt;

        // value-replacement helper (same technique as the M2 corruption tests)
        auto ReplaceSectionValue = [](const std::string& Payload, const char* Key, const char* NewValue,
                std::string& Out) -> bool
        {
                Out = Payload;
                const size_t KeyPos = Out.find(std::string("\"") + Key + "\":");
                if (KeyPos == std::string::npos) { return false; }
                const size_t ValueStart = Out.find(':', KeyPos) + 1;
                const char First = Out[ValueStart];
                size_t ValueEnd = ValueStart;
                if (First == '"')
                {
                        ValueEnd = Out.find('"', ValueStart + 1);
                }
                else if (First == '{' || First == '[')
                {
                        const char Open = First;
                        const char Close = (First == '{') ? '}' : ']';
                        int Depth = 0;
                        for (size_t S = ValueStart; S < Out.size(); ++S)
                        {
                                if (Out[S] == Open) { ++Depth; }
                                else if (Out[S] == Close)
                                {
                                        --Depth;
                                        if (Depth == 0) { ValueEnd = S; break; }
                                }
                        }
                }
                else
                {
                        ValueEnd = Out.find(',', ValueStart) - 1;
                }
                if (ValueEnd == std::string::npos || ValueEnd < ValueStart) { return false; }
                Out.replace(ValueStart, ValueEnd - ValueStart + 1, NewValue);
                return true;
            };

        std::string Err;

        // 1) a corrupt LATER section after a valid village section - the classic
        //    partial-mutation trap: village would apply, then evidence refuses
        std::string Attack;
        TLS_CHECK(ReplaceSectionValue(Alt, "evidence", "\"corrupted\"", Attack));
        TLS_CHECK(!G.LoadFromString(Attack, Err));
        TLS_CHECK_MSG(G.SaveToString() == Session, "corrupt-evidence load refused with the session untouched");

        // 2) deep corruption INSIDE the village section (trust value out of range)
        TLS_CHECK(ReplaceSectionValue(Alt, "value", "999", Attack));
        TLS_CHECK(!G.LoadFromString(Attack, Err));
        TLS_CHECK_MSG(G.SaveToString() == Session, "out-of-range trust load refused with the session untouched");

        // 3) unsupported future version
        std::string Future = Session;
        Future.replace(Future.find("\"save_version\":3"), 16, "\"save_version\":99");
        TLS_CHECK(!G.LoadFromString(Future, Err));
        TLS_CHECK_MSG(G.SaveToString() == Session, "future-version refusal leaves the session untouched");

        // 4) truncated and non-JSON payloads
        TLS_CHECK(!G.LoadFromString(Session.substr(0, Session.size() / 2), Err));
        TLS_CHECK(G.SaveToString() == Session);
        TLS_CHECK(!G.LoadFromString("{not json", Err));
        TLS_CHECK(G.SaveToString() == Session);

        // the session is still alive and playable after every refusal
        G.NotifyCollectEvidence("EVD-RITE-PAPER", "still alive after refusals");
        TLS_CHECK(G.EvidenceCollected("EVD-RITE-PAPER"));

        // control: the uncorrupted alternative world loads fine and rolls forward
        GAlt = MakeLoadedGame();
        if (GAlt)
        {
                TLS_CHECK(GAlt->LoadFromString(Alt, Err));
                TLS_CHECK(GAlt->CurrentDay() == 2);
                TLS_CHECK(GAlt->GetWeather() == EWeather::Rain);
                delete GAlt;
        }
}

void TestQuestFailureBranch(Game& G)
{
        TLS_SECTION("M3.1 regression - expiry failure, consequences, any_of honesty");

        G.NewGame();
        G.AdvanceSimDay();                                          // day 2: C2 opens
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Active);
        TLS_CHECK_MSG(G.Quests().Status("Q-M-C1") == EQuestStatus::Active,
                "a quest without fails_on_expiry stays Active past its window - no fake failure");

        G.AdvanceSimDay();                                          // day 3: C3 opens
        TLS_CHECK(G.Quests().Status("Q-M-C3") == EQuestStatus::Active);
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);
        TLS_CHECK(G.Rumors().NpcKnows("T3-07", "RUM-SHONI-SUSPECT"));

        // hearing the accusation satisfies the HEARD objective only - the
        // any_of ALIBI objective must not be satisfied by the wrong rumor
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07"));
        TLS_CHECK(!ObjectiveDone(G, "OBJ-SHONI-ALIBI"));
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);

        G.AdvanceSimDay();                                          // day 4: the window closes
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Failed);
        TLS_CHECK(G.GetFlag("FLG_SHONI_TAKEN") == 1);
        bool bJournalFailure = false;
        for (const Game::JournalEntry& J : G.Journal())
        {
                if (J.Text.find("Failed: A Day for the Tinker") != std::string::npos) { bJournalFailure = true; }
        }
        TLS_CHECK(bJournalFailure);
        TLS_CHECK_MSG(G.Quests().Status("Q-M-C3") == EQuestStatus::Active,
                "the main thread carries on after the optional failure");

        // the failed state survives the save/load seam exactly
        const std::string S = G.SaveToString();
        Game* GL = MakeLoadedGame();
        TLS_CHECK(GL != nullptr);
        if (GL)
        {
                std::string Err;
                TLS_CHECK_MSG(GL->LoadFromString(S, Err), "failed-quest state loads: " + Err);
                TLS_CHECK(GL->Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Failed);
                TLS_CHECK(GL->GetFlag("FLG_SHONI_TAKEN") == 1);
                TLS_CHECK(GL->SaveToString() == S);
                delete GL;
        }
}

// ---------------------------------------------------------------- entry

void RunAll()
{
        {
                // the loop, twice, from the same default seed: the whole loop -
                // including its internal save/load seam - must be deterministic
                Game* GA = MakeLoadedGame();
                Game* GB = MakeLoadedGame();
                TLS_CHECK(GA != nullptr && GB != nullptr);
                if (GA && GB)
                {
                        RunInvestigationLoop(*GA);
                        RunInvestigationLoop(*GB);
                        TLS_CHECK_MSG(GA->SaveToString() == GB->SaveToString(),
                                "same-seed replay of the whole investigation loop is byte-identical");
                }
                delete GA;
                delete GB;
        }

        {
                Game* G = MakeLoadedGame();
                if (G) { TestRepeatedInteractions(*G); delete G; }
                G = MakeLoadedGame();
                if (G) { TestUnknownIds(*G); delete G; }
                G = MakeLoadedGame();
                if (G) { TestAtomicLoadRefusal(*G); delete G; }
                G = MakeLoadedGame();
                if (G) { TestQuestFailureBranch(*G); delete G; }
        }
}

} // namespace tls_test_investigation
