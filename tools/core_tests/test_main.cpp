// THE LAST SIN: The Sin-Eater - M1
// test_main: standalone unit tests for the game-logic core.
// Build & run: tools/core_tests/run_core_tests.sh (g++; also runs in CI).
// Every test drives the SAME C++ that compiles into the UE module.

#include "tls_test_framework.h"
#include "sim_playthrough.h"

#include "TLSJson.h"
#include "TLSCoreTypes.h"
#include "TLSGameState.h"

#include <cmath>
#include <map>
#include <memory>
#include <set>
#include <string>

using namespace tls;

namespace tls_test_rumors
{
void RunAll();
}

namespace tls_test_quests
{
void RunAll(Game& G);
}

namespace tls_test_settings
{
void RunAll(Game& G);
}

namespace tls_test_investigation
{
void RunAll();
}

namespace tls_test_m32
{
void RunAll();
}

namespace tls_test_m37
{
void RunAll();
}

// Builds a Game with every 05_Narrative data file loaded (evidence, quests,
// sim, rumors, dialogues). Declared in test_fixtures.h - shared by all test
// translation units. The data-loading checks run through the shared framework.
Game* MakeLoadedGame()
{
        Game* G = new Game();
        std::string Err, Content;

        TLS_CHECK_MSG(ReadFileToString("05_Narrative/evidence/evidence_slice.json", Content), "evidence file");
        JsonParseResult P = JsonParse(Content);
        TLS_CHECK_MSG(P.Ok, "evidence json: " + P.Error);
        TLS_CHECK_MSG(G->LoadEvidenceData(P.Value, Err), "evidence load: " + Err);

        TLS_CHECK_MSG(ReadFileToString("05_Narrative/quests/quests_slice.json", Content), "quests file");
        P = JsonParse(Content);
        TLS_CHECK_MSG(P.Ok, "quests json: " + P.Error);
        TLS_CHECK_MSG(G->LoadQuestData(P.Value, Err), "quests load: " + Err);

        TLS_CHECK_MSG(ReadFileToString("05_Narrative/sim/sim_blackthorne.json", Content), "sim file");
        P = JsonParse(Content);
        TLS_CHECK_MSG(P.Ok, "sim json: " + P.Error);
        TLS_CHECK_MSG(G->LoadSimData(P.Value, Err), "sim load: " + Err);

        TLS_CHECK_MSG(ReadFileToString("05_Narrative/rumors/rumors_blackthorne.json", Content), "rumors file");
        P = JsonParse(Content);
        TLS_CHECK_MSG(P.Ok, "rumors json: " + P.Error);
        TLS_CHECK_MSG(G->LoadRumorData(P.Value, Err), "rumor load: " + Err);

        const char* Dialogues[] = {
                "05_Narrative/dialogues/dlg_chr003_gwendolyn_c1.json",
                "05_Narrative/dialogues/dlg_chr004_crane_c1.json",
                "05_Narrative/dialogues/dlg_chr013_coles_c1.json",
                "05_Narrative/dialogues/dlg_chr006_mair_c1.json",
                "05_Narrative/dialogues/dlg_chr017_ifor_c2.json",
        };
        for (const char* Path : Dialogues)
        {
                TLS_CHECK_MSG(ReadFileToString(Path, Content), std::string("dialogue file ") + Path);
                P = JsonParse(Content);
                TLS_CHECK_MSG(P.Ok, std::string("dialogue json ") + Path + ": " + P.Error);
                TLS_CHECK_MSG(G->LoadDialogueData(P.Value, Err), std::string("dialogue load ") + Path + ": " + Err);
        }
        return G;
}

// ---------------------------------------------------------------- JSON

void TestJson()
{
        TLS_SECTION("TLSJson - parser and serializer");

        // round trip on a nested structure
        const std::string Src =
                "{\"day\":2,\"weather\":\"rain\",\"trust\":[{\"npc\":\"CHR-03\",\"value\":20.2}],"
                "\"flags\":{\"A\":1,\"B\":0},\"note\":\"T\\u0177 Uchel\",\"list\":[1,-2.5,3e2],"
                "\"empty\":{},\"arr\":[],\"nul\":null}";
        JsonParseResult R = JsonParse(Src);
        TLS_CHECK(R.Ok);
        TLS_CHECK(R.Value.GetInt("day", 0) == 2);
        TLS_CHECK(R.Value.GetString("weather", "") == "rain");
        TLS_CHECK(R.Value.Find("trust")->At(0)->GetNumber("value", 0.0) == 20.2);
        TLS_CHECK(R.Value.Find("flags")->GetInt("A", 0) == 1);
        TLS_CHECK(R.Value.GetString("note", "").find("\xc5\xb7") != std::string::npos); // UTF-8 w-circumflex
        TLS_CHECK(R.Value.Find("list")->At(2)->AsNumber() == 300.0);
        TLS_CHECK(R.Value.Find("empty")->IsObject() && R.Value.Find("empty")->Size() == 0);
        TLS_CHECK(R.Value.Find("arr")->IsArray() && R.Value.Find("arr")->Size() == 0);
        TLS_CHECK(R.Value.Find("nul")->IsNull());

        const std::string Ser = JsonSerialize(R.Value, false);
        JsonParseResult R2 = JsonParse(Ser);
        TLS_CHECK(R2.Ok);
        TLS_CHECK(JsonSerialize(R2.Value, false) == Ser);   // deterministic

        // malformed inputs rejected with locations
        const char* Bad[] = { "{\"a\":}", "[1,2", "\"open", "{},trailing", "{\"a\":1,}", "{\"a\":\"\\q\"}", "nul" };
        for (const char* B : Bad)
        {
                JsonParseResult RB = JsonParse(B);
                TLS_CHECK_MSG(!RB.Ok, std::string("must reject: ") + B);
                if (!RB.Ok) { TLS_CHECK_MSG(RB.Line >= 1, "error carries a line number"); }
        }

        // unicode escape + surrogate pairs
        JsonParseResult U = JsonParse("{\"s\":\"\\u0633\\u0644\\u0645 \\ud83d\\ude00\"}");
        TLS_CHECK(U.Ok);
        TLS_CHECK(U.Value.GetString("s", "").size() == 11);   // 3 arabic (2B each) + space + 4-byte emoji
}

// ---------------------------------------------------------------- welsh layer

void TestWelshLayer()
{
        TLS_SECTION("Welsh language layer (GAME_BIBLE 6.2.5)");

        bool bLesson = false;
        std::string Out = RenderDialogueText("She says: [w1:Bore da], and later [w3:Diolch].", 0, bLesson);
        TLS_CHECK(bLesson);
        TLS_CHECK(Out.find("#####") != std::string::npos);
        TLS_CHECK(Out.find("######") != std::string::npos);    // "Diolch" = 6 hashes
        TLS_CHECK(Out.find("Welsh") == std::string::npos);

        Out = RenderDialogueText("[w1:Bore da]", 1, bLesson);
        TLS_CHECK(!bLesson);
        TLS_CHECK(Out.find("Bore da (Welsh)") != std::string::npos);

        Out = RenderDialogueText("[w3:Diolch]", 2, bLesson);
        TLS_CHECK(bLesson);                                     // level 2 < required 3
        Out = RenderDialogueText("[w3:Diolch]", 3, bLesson);
        TLS_CHECK(!bLesson);
        TLS_CHECK(Out.find("Diolch (Welsh)") != std::string::npos);

        // plain text untouched
        Out = RenderDialogueText("No markers here.", 0, bLesson);
        TLS_CHECK(!bLesson && Out == "No markers here.");
}

// ---------------------------------------------------------------- evidence

void TestEvidenceRules(Game& G)
{
        TLS_SECTION("Evidence system - custody, gating, contradictions");

        G.NewGame();

        // collect -> examine order enforced
        std::string R;
        TLS_CHECK(!G.Evidence().IsCollected("EVD-DISH"));
        G.NotifyExamineEvidence("EVD-DISH", &R);            // not collected yet
        TLS_CHECK(!G.Evidence().IsExamined("EVD-DISH"));
        G.NotifyCollectEvidence("EVD-DISH", "from the boundary stone");
        TLS_CHECK(G.Evidence().IsCollected("EVD-DISH"));

        // restorable page: full text only after restoration
        G.NotifyCollectEvidence("EVD-TORN-PAGE", "from the floor stone");
        G.NotifyExamineEvidence("EVD-TORN-PAGE", &R);
        TLS_CHECK_MSG(R.find("tear runs through") != std::string::npos, "unrestored page hides its detail");
        G.NotifyRestorePage("EVD-TORN-PAGE", &R);
        TLS_CHECK_MSG(R.find("The bread stayed on the stone") != std::string::npos, "restored page reveals the marginal note");
        G.NotifyExamineEvidence("EVD-TORN-PAGE", &R);
        TLS_CHECK_MSG(R.find("Nott") != std::string::npos, "examined-after-restore shows the list fragment");

        // non-restorable documentary examines fully
        G.NotifyCollectEvidence("EVD-GRAVE", "register page");
        G.NotifyExamineEvidence("EVD-GRAVE", &R);
        TLS_CHECK_MSG(R.find("Bellamy") != std::string::npos, "register detail available without restoration");

        // links: examine gate, unknown pair, self pair
        std::string Msg;
        std::vector<std::string> NI;
        G.NotifyDrawLink("EVD-DISH", "EVD-TORN-PAGE", &Msg, &NI);   // DISH examined? no yet in this test
        // (DISH not examined here - both must be examined)
        TLS_CHECK_MSG(Msg.find("examine both pages") != std::string::npos || NI.empty(), "gate message or no insight");
        G.NotifyExamineEvidence("EVD-DISH", &R);
        G.NotifyDrawLink("EVD-DISH", "EVD-DISH", &Msg, &NI);
        TLS_CHECK_MSG(Msg.find("testify against itself") != std::string::npos, "self-link rejected");
        G.NotifyDrawLink("EVD-DISH", "EVD-GRAVE", &Msg, &NI);
        TLS_CHECK_MSG(Msg.find("No established connection") != std::string::npos, "unknown pair is marked unlinked");
        TLS_CHECK(NI.empty());
}

// ---------------------------------------------------------------- village sim

void TestVillageSim(Game& G)
{
        TLS_SECTION("Village simulation - schedules, tension, trust math");

        // schedule integrity for every NPC (NPC_SIMULATION 10.1-style rule):
        // full 24h coverage without gaps + at least 5h of sleep
        const auto& Npcs = G.Village().Npcs();
        int BgCount = 0;
        for (const auto& KV : Npcs)
        {
                const NPCDef& N = KV.second;
                // both schedules (plain + tension) must cover the day
                for (const std::vector<ScheduleSegment>* Segs : { &N.Schedule, &N.ScheduleTension })
                {
                        if (Segs->empty()) { continue; }
                        int SleepHours = 0, Cursor = 0;
                        bool bFirst = true;
                        for (const ScheduleSegment& S : *Segs)
                        {
                                if (bFirst)
                                {
                                        TLS_CHECK_MSG(S.FromHour <= 8, N.Id + " day starts by 08:00");
                                        SleepHours += S.FromHour;          // pre-dawn counts as sleep
                                        bFirst = false;
                                }
                                else
                                {
                                        TLS_CHECK_MSG(S.FromHour == Cursor, "no internal gaps in " + N.Id + " schedule");
                                }
                                Cursor = S.ToHour;
                                if (S.Activity == "sleep") { SleepHours += S.ToHour - S.FromHour; }
                        }
                        TLS_CHECK_MSG(Cursor == 24, N.Id + " runs to midnight");
                        TLS_CHECK_MSG(SleepHours >= 5, N.Id + " sleeps >= 5h");
                }
                if (N.Tier == 3) { ++BgCount; }
        }
        TLS_CHECK(BgCount == 12);   // M1 scope: 12 background NPCs with schedules

        // zone queries: plain vs tension variant
        G.NewGame();   // day 1, tension 1
        TLS_CHECK(G.Village().NpcZoneAt("CHR-03", 9) == "AREA-INN");
        TLS_CHECK(G.Village().NpcZoneAt("CHR-04", 20) == "AREA-CHURCHYARD");   // tower at evening
        TLS_CHECK(G.Village().NpcZoneAt("T3-03", 9) == "AREA-RIVERBANK");
        TLS_CHECK(G.Village().NpcZoneAt("T3-12", 2) == "AREA-COTTAGE");        // the night window

        // trust math: tone weight + relationship bias (NPC_SIMULATION 3)
        G.NewGame();
        // Coles: bias 0.15, gentle weight +2 -> delta (0+2)*(1-0.15)=1.7
        const double Applied = G.VillageMut().ApplyTrustDelta("CHR-13", 0.0, ETone::Gentle);
        TLS_CHECK_MSG(std::fabs(Applied - 1.7) < 1e-9, "gentle on Coles: (0+2)*(1-0.15) = 1.7");
        // Gwendolyn: bias 0.35, pressing -3 -> (0-3)*0.65 = -1.95
        const double Applied2 = G.VillageMut().ApplyTrustDelta("CHR-03", 0.0, ETone::Pressing);
        TLS_CHECK_MSG(std::fabs(Applied2 + 1.95) < 1e-9, "pressing on Gwen: (0-3)*(1-0.35) = -1.95");
        // clamp at -100/+100
        G.VillageMut().ApplyTrustDelta("CHR-13", -300.0, ETone::Silent);
        TLS_CHECK(G.GetTrust("CHR-13") == -100.0);

        // spillover: inn gain -> church loss
        G.NewGame();
        const double CraneBefore = G.GetTrust("CHR-04");
        G.VillageMut().ApplyTrustDelta("CHR-03", 10.0, ETone::Formal);   // (10+1)*0.65 = 7.15
        const double CraneAfter = G.GetTrust("CHR-04");
        TLS_CHECK_MSG(CraneAfter < CraneBefore, "church trust bleeds when the inn gains");
        TLS_CHECK_MSG(std::fabs((CraneBefore - CraneAfter) - 7.15 * 0.15) < 1e-9, "spill = gain * -0.15");
}

// ---------------------------------------------------------------- quests + dialogue

void TestQuestAndDialogueRules(Game& G)
{
        TLS_SECTION("Quests - day windows, optional objectives, completion flags");

        // optional objective does not block completion (the player who talks to nobody)
        G.NewGame();
        G.NotifyReachArea("AREA-CHURCHYARD");
        G.NotifyObserveEvidence("EVD-GRAVE");
        G.NotifyReachArea("AREA-BOUNDARY");
        G.NotifyCollectEvidence("EVD-DISH", "x");
        G.NotifyReachArea("AREA-COTTAGE");
        G.NotifyCollectEvidence("EVD-LEDGER", "x");
        G.NotifyCollectEvidence("EVD-RITE-PAPER", "x");
        G.NotifyCollectEvidence("EVD-TORN-PAGE", "x");
        std::string Err;
        G.BeginDialogue("DLG-GWENDOLYN-C1", Err);
        // pick the formal attendance line (ends the tree? no - it returns to hub; then H6)
        TLS_CHECK(G.DialogueRunning());
        { std::string EnteredNode; TLS_CHECK(G.PickDialogueChoice(1, EnteredNode, Err)); }   // G02 formal attendance -> hub
        // now end it
        {
                std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
                for (size_t I = 0; I < Avail.size(); ++I)
                {
                        if (Avail[I]->Id == "H6") { std::string EN; G.PickDialogueChoice(I, EN, Err); break; }
                }
        }
        TLS_CHECK(G.GetFlag("MET_GWENDOLYN") == 1);
        G.NotifyRestorePage("EVD-TORN-PAGE");
        std::string R;
        G.NotifyExamineEvidence("EVD-DISH", &R);
        G.NotifyExamineEvidence("EVD-LEDGER", &R);
        G.NotifyExamineEvidence("EVD-TORN-PAGE", &R);
        // no Gwendolyn trust path taken -> guinea evidence missing -> SINLIST must still be reachable?
        // (the three-path rule: gravedigger route also works - COLES-RITE was never given here either.
        //  So this run uses path 2: DISH + TORN-PAGE for REFUSAL, and SINLIST needs a testimonial.)
        // The design intent: SINLIST paths all need one testimonial source; without any testimony the
        // objective legitimately stays open - the day cannot end. That is the designed dead-end guard:
        std::vector<std::string> NI;
        std::string Msg;
        G.NotifyDrawLink("EVD-DISH", "EVD-TORN-PAGE", &Msg, &NI);
        TLS_CHECK(G.InsightKnown("INS-REFUSAL"));
        TLS_CHECK(!G.InsightKnown("INS-SINLIST"));
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Active);
        std::string Reason;
        TLS_CHECK(!G.NotifySleep(Reason));

        // ...but the gravedigger route exists: get his testimony and the day closes
        G.BeginDialogue("DLG-COLES-C1", Err);
        {
                std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
                for (size_t I = 0; I < Avail.size(); ++I)
                {
                        if (Avail[I]->Id == "B3") { std::string EN; G.PickDialogueChoice(I, EN, Err); break; }   // silent listen
                }
        }
        // NODE_BABBLE auto-nexts to hub
        {
                std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
                for (size_t I = 0; I < Avail.size(); ++I)
                {
                        if (Avail[I]->Id == "BH1") { std::string EN; G.PickDialogueChoice(I, EN, Err); break; }  // last months
                }
        }
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-RITE"));
        G.NotifyExamineEvidence("EVD-COLES-RITE", &R);
        G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-COLES-RITE", &Msg, &NI);
        TLS_CHECK(G.InsightKnown("INS-SINLIST"));
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_LEDGER_FOUND") == 1);
        TLS_CHECK(G.NotifySleep(Reason));
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Active);

        TLS_SECTION("Dialogue - conditions and reactions");
        // evidence presentation with DENY reaction records the contradiction on the chain
        G.BeginDialogue("DLG-CRANE-C1", Err);
        {
                std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
                bool bFound = false;
                for (size_t I = 0; I < Avail.size(); ++I)
                {
                        if (Avail[I]->Id == "C03") { bFound = true; std::string EN; G.PickDialogueChoice(I, EN, Err); break; }
                }
                TLS_CHECK_MSG(bFound, "C03 present-dish choice is available when the dish is carried");
        }
        const tls::EvidenceRuntime* Rt2 = G.Evidence().State("EVD-DISH");
        bool bDenyAfter = false;
        for (const std::string& C : Rt2->ChainOfCustody) { if (C.find("denied it") != std::string::npos) { bDenyAfter = true; } }
        TLS_CHECK_MSG(bDenyAfter, "Crane's denial is recorded on the dish's chain of custody");
}

// ---------------------------------------------------------------- M2.1 game integration

void TestRumorGameIntegration(Game& G)
{
        TLS_SECTION("M2.1 rumors - game integration: seeding, tools, conditions");

        G.NewGame();

        // day-1 rumors enter with their seeds; later-day rumors stay dark
        TLS_CHECK(G.Rumors().NpcKnows("T3-06", "RUM-HUNGER-RETURNS"));
        TLS_CHECK(G.Rumors().NpcKnows("T3-03", "RUM-HUNGER-RETURNS"));
        TLS_CHECK(G.Rumors().NpcKnows("T3-05", "RUM-GUINEA-SILENCE"));
        TLS_CHECK(G.Rumors().KnowerCount("RUM-NOTT-SALT") == 0);        // born day 2
        TLS_CHECK(G.Rumors().KnowerCount("RUM-SHONI-SUSPECT") == 0);    // born day 3
        TLS_CHECK(G.Rumors().KnowerCount("RUM-SHONI-HILL") == 0);       // leak-only

        // condition context reads the same truth the engine holds
        TLS_CHECK(G.NpcKnowsRumor("T3-06", "RUM-HUNGER-RETURNS"));
        TLS_CHECK(!G.NpcKnowsRumor("CHR-03", "RUM-HUNGER-RETURNS"));
        TLS_CHECK(!G.PlayerHeardRumor("RUM-HUNGER-RETURNS"));

        // player tool: heard (journal entry recorded once)
        {
                const size_t JournalBefore = G.Journal().size();
                TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06"));
                TLS_CHECK(!G.NotifyPlayerHeardRumor("RUM-GHOST", "T3-06"));
                TLS_CHECK(G.PlayerHeardRumor("RUM-HUNGER-RETURNS"));
                TLS_CHECK(G.Journal().size() == JournalBefore + 1);
                TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06"));   // no duplicate journal
                TLS_CHECK(G.Journal().size() == JournalBefore + 1);
        }

        // player tool: witness event registers direct testimony, duplicates ignored
        {
                std::string Err;
                TLS_CHECK(G.NotifyWitnessEvent("RUM-SHONI-HILL", 1, 10, "AREA-INN", { "CHR-03" }, Err));
                const RumorKnowledge* KW = G.Rumors().NpcKnowledge("CHR-03", "RUM-SHONI-HILL");
                TLS_CHECK_MSG(KW != nullptr && KW->Kind == ETestimonyKind::Direct,
                        "witness of a world event holds direct testimony");
                const int Before = G.Rumors().KnowerCount("RUM-SHONI-HILL");
                TLS_CHECK(G.NotifyWitnessEvent("RUM-SHONI-HILL", 1, 10, "AREA-INN", { "CHR-03" }, Err));
                TLS_CHECK(G.Rumors().KnowerCount("RUM-SHONI-HILL") == Before);   // no duplicate event
        }

        // player tool: the anonymous leak into the market square at noon
        {
                std::string Err;
                const int Heard = G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-SQUARE", Err);
                TLS_CHECK_MSG(Heard >= 1, "the leak reaches somebody in the square at noon");
                bool PlayerInChain = false;
                for (const RumorTransmission& T : G.Rumors().TransmissionLog())
                {
                        if (T.RumorId == "RUM-SHONI-HILL" && T.FromNpc == "PLAYER") { PlayerInChain = true; }
                }
                TLS_CHECK(PlayerInChain);
                // the leak cannot land in a non-gossip zone
                TLS_CHECK(G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-COTTAGE", Err) == -1);
        }

        // player tool: public denial raises reputation and dents every holder
        {
                int Holders = 0;
                for (const std::string& R : G.Rumors().ActiveRumorIds()) { Holders += G.Rumors().KnowerCount(R); }
                const double RepBefore = G.Village().Reputation();
                const int Affected = G.NotifyPlayerRumorDenial();
                TLS_CHECK(Affected == Holders);
                TLS_CHECK_MSG(G.Village().Reputation() == RepBefore + 2.0, "the village rewards a public stand");
        }

        // gossip tick: transmissions stay inside gossip zones
        {
                auto Result = G.TickVillageGossip(1, 8);
                for (const RumorTransmission& T : Result.NewTransmissions)
                {
                        TLS_CHECK_MSG(G.Rumors().IsGossipZone(T.Zone), "transmission zone is a gossip zone");
                }
        }
}

// ---------------------------------------------------------------- M2.1 seven-day simulation

namespace
{

struct SimTrace
{
        int Transmissions = 0;
        std::map<int, int> NewKnowersByDay;
        bool bZonesClean = true;
        bool bMairNeverSpoke = true;
        bool bBrookSilentOnTenseDays = true;
        int MaxKnowersOfOneRumor = 0;
};

SimTrace RunSevenDaySim(Game& G)
{
        SimTrace Trace;
        const std::set<std::string> Gossip = { "AREA-SQUARE", "AREA-INN", "AREA-CHURCH", "AREA-CHURCHYARD" };
        for (int Day = 1; Day <= 7; ++Day)
        {
                RumorSystem::TickResult Result;
                int DayNewKnowers = 0;
                for (int Hour = 8; Hour <= 21; ++Hour)
                {
                        Result = G.TickVillageGossip(Day, Hour);
                        DayNewKnowers += Result.NewKnowersToday;
                        for (const RumorTransmission& T : Result.NewTransmissions)
                        {
                                ++Trace.Transmissions;
                                if (!Gossip.count(T.Zone)) { Trace.bZonesClean = false; }
                                if (T.FromNpc == "CHR-06") { Trace.bMairNeverSpoke = false; }            // reticence 0.9
                                if (T.FromNpc == "T3-11" && Day >= 2) { Trace.bBrookSilentOnTenseDays = false; }  // 0.6+0.15 tension
                        }
                }
                Trace.NewKnowersByDay[Day] = DayNewKnowers;
                for (const std::string& R : G.Rumors().ActiveRumorIds())
                {
                        Trace.MaxKnowersOfOneRumor = std::max(Trace.MaxKnowersOfOneRumor, G.Rumors().KnowerCount(R));
                }
                if (Day < 7) { G.AdvanceSimDay(); }
        }
        return Trace;
}

} // anonymous namespace

void TestSevenDayRumorSimulation(Game& G)
{
        TLS_SECTION("M2.1 rumors - seven-day headless village simulation (NPC_SIMULATION 10)");

        G.NewGame();
        const SimTrace Trace = RunSevenDaySim(G);

        // spread stays inside the daily cap: floor(0.30 * 17) = 5 new knowers/day
        for (const auto& KV : Trace.NewKnowersByDay)
        {
                TLS_CHECK_MSG(KV.second <= 5, "day " + std::to_string(KV.first) + " new knowers "
                        + std::to_string(KV.second) + " <= cap 5");
        }
        TLS_CHECK_MSG(Trace.Transmissions > 0, "gossip actually happened over seven days");
        TLS_CHECK(Trace.bZonesClean);
        TLS_CHECK_MSG(Trace.bMairNeverSpoke, "Mair (reticence 0.9) never carries gossip");
        TLS_CHECK_MSG(Trace.bBrookSilentOnTenseDays, "John Brook (0.6 + tension 3*0.05 = 0.75) falls silent on tense days");
        TLS_CHECK_MSG(Trace.MaxKnowersOfOneRumor < 17, "no rumor reaches the whole village instantly");

        // rumors born later actually activate on their day
        TLS_CHECK_MSG(G.Rumors().KnowerCount("RUM-NOTT-SALT") > 0, "the day-2 mill death entered circulation");
        TLS_CHECK_MSG(G.Rumors().KnowerCount("RUM-SHONI-SUSPECT") > 0, "the day-3 constable theory entered circulation");

        // provenance integrity after seven days of churn: every chain step is a real transfer
        bool AllReal = true;
        for (const auto& KV : G.Rumors().Defs())
        {
                for (const std::string& Holder : G.Rumors().NpcsKnowing(KV.first))
                {
                        for (const RumorTransmission& Step : G.Rumors().TraceProvenance(KV.first, Holder))
                        {
                                bool Found = false;
                                for (const RumorTransmission& T : G.Rumors().TransmissionLog())
                                {
                                        if (T.RumorId == Step.RumorId && T.FromNpc == Step.FromNpc && T.ToNpc == Step.ToNpc
                                                && T.Day == Step.Day && T.Hour == Step.Hour) { Found = true; break; }
                                }
                                if (!Found) { AllReal = false; }
                        }
                }
        }
        TLS_CHECK_MSG(AllReal, "every provenance chain after 7 days is made of recorded transmissions");

        // determinism: an identical replay reproduces the identical state
        {
                Game* G2 = MakeLoadedGame();
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        RunSevenDaySim(*G2);
                        TLS_CHECK_MSG(JsonSerialize(G.Rumors().SerializeState(), false) == JsonSerialize(G2->Rumors().SerializeState(), false),
                                "two identical runs produce identical rumor history");
                        delete G2;
                }
        }

        // a different seed tells a different story (deterministic divergence)
        {
                Game* G3 = MakeLoadedGame();
                TLS_CHECK(G3 != nullptr);
                if (G3)
                {
                        G3->NewGame();
                        G3->SetSimRngState(kDefaultSimSeed ^ 0xA5A5A5A5A5A5A5A5ULL);
                        RunSevenDaySim(*G3);
                        TLS_CHECK_MSG(JsonSerialize(G.Rumors().SerializeState(), false) != JsonSerialize(G3->Rumors().SerializeState(), false),
                                "a different sim seed diverges");
                        delete G3;
                }
        }
}

// ---------------------------------------------------------------- M2 save version gate

void TestSaveVersionGate(Game& G)
{
        TLS_SECTION("M2 save - version gate, legacy v1, and the save/load/continue seam");

        G.NewGame();
        G.TickVillageGossip(1, 8);
        G.TickVillageGossip(1, 9);
        G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06");
        const std::string V2 = G.SaveToString();

        // future version refused with a clear message
        {
                Game* G2 = MakeLoadedGame();
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        std::string VFuture = V2;
                        VFuture.replace(VFuture.find("\"save_version\":3"), 16, "\"save_version\":4");
                        std::string Err;
                        TLS_CHECK_MSG(!G2->LoadFromString(VFuture, Err), "a save from a newer version is refused");
                        TLS_CHECK_MSG(Err.find("save_version") != std::string::npos, "the error names the version problem");
                        delete G2;
                }
        }

        // the CURRENT version loads (M3.7: 3 = case facts + deduction layer)
        {
                Game* G2 = MakeLoadedGame();
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        std::string Err;
                        TLS_CHECK_MSG(G2->LoadFromString(V2, Err), "a v3 payload reloads: " + Err);
                        delete G2;
                }
        }

        // v2 missing sim_rng refused
        {
                Game* G2 = MakeLoadedGame();
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        std::string Mangled = V2;
                        const size_t Key = Mangled.find("\"sim_rng\":");
                        TLS_CHECK(Key != std::string::npos);
                        if (Key != std::string::npos) { Mangled.erase(Key, 29); }   // "sim_rng":"<16hex>",
                        std::string Err;
                        TLS_CHECK_MSG(!G2->LoadFromString(Mangled, Err), "v2 without the sim rng is refused");
                        delete G2;
                }
        }

        // legacy v1 loads, rumor layer starts clean
        {
                Game* G2 = MakeLoadedGame();
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        std::string V1 = V2;
                        V1.replace(V1.find("\"save_version\":3"), 16, "\"save_version\":1");
                        // strip the v2-only payloads (rumors object, then the rng key)
                        const size_t RumorKey = V1.find("\"rumors\":");
                        TLS_CHECK(RumorKey != std::string::npos);
                        size_t Scan = V1.find('{', RumorKey), Depth = 0, End = Scan;
                        for (; Scan < V1.size(); ++Scan)
                        {
                                if (V1[Scan] == '{') { ++Depth; }
                                else if (V1[Scan] == '}') { --Depth; if (Depth == 0) { End = Scan; break; } }
                        }
                        V1.erase(RumorKey, End - RumorKey + 2);   // object + trailing comma
                        const size_t RngKey = V1.find("\"sim_rng\":");
                        TLS_CHECK(RngKey != std::string::npos);
                        if (RngKey != std::string::npos) { V1.erase(RngKey, 29); }   // "sim_rng":"<16hex>",
                        std::string Err;
                        TLS_CHECK_MSG(G2->LoadFromString(V1, Err), "legacy v1 payload loads: " + Err);
                        if (G2->LoadFromString(V1, Err))
                        {
                                TLS_CHECK_MSG(G2->Rumors().ActiveRumorIds().empty(), "v1 has no rumor history - layer starts clean");
                                TLS_CHECK(!G2->PlayerHeardRumor("RUM-HUNGER-RETURNS"));
                        }
                        delete G2;
                }
        }

        // full round trip: save mid-simulation, load into a fresh game, continue -
        // both roads must reach the identical world (M2.2 core guarantee)
        {
                Game* GA = MakeLoadedGame();
                Game* GB = MakeLoadedGame();
                TLS_CHECK(GA && GB);
                if (GA && GB)
                {
                        GA->NewGame();
                        for (int Hour = 8; Hour <= 12; ++Hour) { GA->TickVillageGossip(1, Hour); }
                        const std::string Mid = GA->SaveToString();

                        GB->NewGame();
                        std::string Err;
                        TLS_CHECK_MSG(GB->LoadFromString(Mid, Err), "mid-sim v2 load: " + Err);
                        TLS_CHECK_MSG(GB->SimRngState() == GA->SimRngState(), "the sim rng state travels with the save");
                        TLS_CHECK_MSG(JsonSerialize(GB->Rumors().SerializeState(), false) == JsonSerialize(GA->Rumors().SerializeState(), false),
                                "rumor state identical after load");

                        // continue both worlds for the rest of the day + two more days
                        for (int Hour = 13; Hour <= 21; ++Hour) { GA->TickVillageGossip(1, Hour); GB->TickVillageGossip(1, Hour); }
                        GA->AdvanceSimDay(); GB->AdvanceSimDay();
                        for (int Hour = 8; Hour <= 21; ++Hour) { GA->TickVillageGossip(2, Hour); GB->TickVillageGossip(2, Hour); }
                        GA->AdvanceSimDay(); GB->AdvanceSimDay();
                        for (int Hour = 8; Hour <= 21; ++Hour) { GA->TickVillageGossip(3, Hour); GB->TickVillageGossip(3, Hour); }

                        TLS_CHECK_MSG(JsonSerialize(GA->Rumors().SerializeState(), false) == JsonSerialize(GB->Rumors().SerializeState(), false),
                                "save -> load -> continue equals never interrupted (zero drift)");
                        TLS_CHECK_MSG(JsonSerialize(GA->Save(), false) == JsonSerialize(GB->Save(), false),
                                "the whole world state is identical after the save/load seam");
                        delete GA; delete GB;
                }
        }
}

// ---------------------------------------------------------------- M2.2 five-point save/load

namespace
{

// ticks the world forward from the CURRENT village day/hour to the end of day 7
void RunSimForward(Game& G, int FromHour)
{
        const int StartDay = G.Village().Day();
        for (int Hour = FromHour; Hour <= 21; ++Hour) { G.TickVillageGossip(StartDay, Hour); }
        for (int Day = StartDay + 1; Day <= 7; ++Day)
        {
                G.AdvanceSimDay();
                for (int Hour = 8; Hour <= 21; ++Hour) { G.TickVillageGossip(Day, Hour); }
        }
}

} // anonymous namespace

void TestFivePointSaveLoad(Game& G)
{
        TLS_SECTION("M2.2 save - five-point save/load round trip, zero drift (NPC_SIMULATION 10.2)");

        struct SavePoint { int Day; int Hour; const char* Label; };
        const SavePoint Points[] = {
                { 1, 10, "day 1 mid-morning" },
                { 2, 14, "day 2 afternoon (tension 3)" },
                { 3, 9,  "day 3 morning (shoni rumor born)" },
                { 5, 12, "day 5 noon" },
                { 7, 18, "day 7 evening" },
        };

        for (const SavePoint& P : Points)
        {
                // drive a fresh world up to the save point
                Game* GA = MakeLoadedGame();
                TLS_CHECK(GA != nullptr);
                if (!GA) { return; }
                GA->NewGame();
                for (int Day = 1; Day < P.Day; ++Day)
                {
                        for (int Hour = 8; Hour <= 21; ++Hour) { GA->TickVillageGossip(Day, Hour); }
                        GA->AdvanceSimDay();
                }
                for (int Hour = 8; Hour < P.Hour; ++Hour) { GA->TickVillageGossip(P.Day, Hour); }

                const std::string Payload = GA->SaveToString();

                // load into a fresh world, then run BOTH to the end of day 7
                Game* GB = MakeLoadedGame();
                TLS_CHECK(GB != nullptr);
                if (!GB) { delete GA; return; }
                GB->NewGame();
                std::string Err;
                TLS_CHECK_MSG(GB->LoadFromString(Payload, Err), std::string(P.Label) + " load: " + Err);
                RunSimForward(*GA, P.Hour);
                RunSimForward(*GB, P.Hour);

                TLS_CHECK_MSG(JsonSerialize(GA->Save(), false) == JsonSerialize(GB->Save(), false),
                        std::string(P.Label) + ": interrupted and loaded worlds end identical");
                TLS_CHECK_MSG(JsonSerialize(GA->Rumors().SerializeState(), false) == JsonSerialize(GB->Rumors().SerializeState(), false),
                        std::string(P.Label) + ": rumor history identical after the seam");
                TLS_CHECK_MSG(GA->SimRngState() == GB->SimRngState(),
                        std::string(P.Label) + ": sim rng streams re-converged");
                delete GA; delete GB;
        }
}

// ---------------------------------------------------------------- M2.2 corrupt subsystem payloads

void TestCorruptSubsystemPayloads(Game& G)
{
        TLS_SECTION("M2.2 save - corrupt subsystem payloads refused, session state intact");

        G.NewGame();
        G.TickVillageGossip(1, 8);
        G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06");
        const std::string Good = G.SaveToString();

        // helper lambda: corrupt a top-level key's value, try to load, verify refusal
        auto CorruptAndTry = [&Good](const char* Key, const char* Replacement, const char* What)
        {
                Game* G2 = MakeLoadedGame();
                if (!G2) { TLS_CHECK_MSG(false, "fixture"); return; }
                G2->NewGame();
                std::string Mangled = Good;
                const size_t KeyPos = Mangled.find(std::string("\"") + Key + "\":");
                TLS_CHECK_MSG(KeyPos != std::string::npos, std::string("found key ") + Key);
                if (KeyPos != std::string::npos)
                {
                        const size_t ValueStart = Mangled.find(':', KeyPos) + 1;
                        // find the end of the current value: strings end at the closing quote,
                        // objects/arrays at the matching brace - Replacement carries its own value
                        const char First = Mangled[ValueStart];
                        size_t ValueEnd = ValueStart;
                        if (First == '"')
                        {
                                ValueEnd = Mangled.find('"', ValueStart + 1);
                        }
                        else if (First == '{' || First == '[')
                        {
                                const char Open = First, Close = (First == '{') ? '}' : ']';
                                int Depth = 0;
                                for (size_t S = ValueStart; S < Mangled.size(); ++S)
                                {
                                        if (Mangled[S] == Open) { ++Depth; }
                                        else if (Mangled[S] == Close) { --Depth; if (Depth == 0) { ValueEnd = S; break; } }
                                }
                        }
                        else
                        {
                                ValueEnd = Mangled.find(',', ValueStart) - 1;
                                if (Mangled[ValueEnd + 1] != ',') { ValueEnd = Mangled.find('}', ValueStart) - 1; }
                        }
                        Mangled.replace(ValueStart, ValueEnd - ValueStart + 1, Replacement);
                }
                std::string Err;
                TLS_CHECK_MSG(!G2->LoadFromString(Mangled, Err), std::string("refused: ") + What);
                // the refused load must not have wrecked the session's existing state
                TLS_CHECK_MSG(G2->Rumors().NpcKnows("T3-06", "RUM-HUNGER-RETURNS"),
                        std::string(What) + ": session rumor state survives a refused load");
                TLS_CHECK_MSG(G2->Village().Day() == 1, std::string(What) + ": village state survives");
                delete G2;
        };

        CorruptAndTry("village", "5", "village payload replaced by a number");
        CorruptAndTry("evidence", "[]", "evidence payload replaced by an array");
        CorruptAndTry("quests", "\"gone\"", "quests payload replaced by a string");
        CorruptAndTry("rumors", "{\"knowledge\":{\"T3-06\":[{\"rumor\":\"RUM-GHOST\"}]}}", "rumors referencing an unknown rumor");
        CorruptAndTry("flags", "3", "flags payload replaced by a number");
        CorruptAndTry("reached_areas", "{\"AREA-INN\":1}", "reached_areas replaced by an object");
        CorruptAndTry("dialogue_history", "7", "dialogue_history replaced by a number");
        CorruptAndTry("journal", "{\"day\":2}", "journal replaced by an object");

        // deep corruption: a trust value out of range inside the village payload
        {
                Game* G2 = MakeLoadedGame();
                if (!G2) { TLS_CHECK_MSG(false, "fixture"); return; }
                G2->NewGame();
                std::string Mangled = Good;
                const size_t TrustPos = Mangled.find("\"trust\":[");
                TLS_CHECK(TrustPos != std::string::npos);
                if (TrustPos != std::string::npos)
                {
                        const size_t ValuePos = Mangled.find("\"value\":", TrustPos);
                        TLS_CHECK(ValuePos != std::string::npos);
                        if (ValuePos != std::string::npos)
                        {
                                Mangled.replace(ValuePos, 8, "\"value\":999");
                        }
                }
                std::string Err;
                TLS_CHECK_MSG(!G2->LoadFromString(Mangled, Err), "village trust value out of range refused");
                delete G2;
        }
}

// ---------------------------------------------------------------- M2.5 expanded world integration

std::unique_ptr<VillageState> MakeMiniVillage(const std::string& Json, std::string& Err)
{
        JsonParseResult P = JsonParse(Json);
        if (!P.Ok) { Err = P.Error; return nullptr; }
        auto V = std::make_unique<VillageState>();
        if (!V->Load(P.Value, Err)) { return nullptr; }
        return V;
}

void TestExpandedWorldZones()
{
        TLS_SECTION("M2.5 world - the engine consumes the expanded districts D5-D11");

        // the real world file defines the areas; the core consumes zone STRINGS
        std::string Content;
        TLS_CHECK_MSG(ReadFileToString("05_Narrative/world/blackthorne_blockout.json", Content), "world file");
        JsonParseResult P = JsonParse(Content);
        TLS_CHECK_MSG(P.Ok, "world json: " + P.Error);
        std::set<std::string> WorldAreas;
        std::set<std::string> Districts;
        if (const JsonValue* Areas = P.Value.Find("areas"))
        {
                for (size_t I = 0; I < Areas->Size(); ++I)
                {
                        const JsonValue* A = Areas->At(I);
                        if (!A) { continue; }
                        WorldAreas.insert(A->GetString("id", ""));
                        Districts.insert(A->GetString("district", ""));
                }
        }
        TLS_CHECK(WorldAreas.count("AREA-SWAMP") && WorldAreas.count("AREA-MINE") && WorldAreas.count("AREA-MOOR")
                && WorldAreas.count("AREA-PLAS") && WorldAreas.count("AREA-CHAPEL") && WorldAreas.count("AREA-POORHOUSE"));
        for (int I = 0; I <= 11; ++I) { TLS_CHECK_MSG(Districts.count("D" + std::to_string(I)) == 1, "district D" + std::to_string(I) + " present"); }

        // a villager scheduled into the new districts resolves like any zone
        std::string Err;
        const char* Explorer = R"json({
          "npcs": [
            { "id": "W", "name": "Walker", "tier": 3, "faction": "none", "initial_trust": 0, "relationship_bias": 0.1,
              "tone_weights": { "silent": 0 },
              "schedule": [ { "from_hour": 8, "to_hour": 12, "zone": "AREA-PLAS", "activity": "errand" },
                            { "from_hour": 12, "to_hour": 16, "zone": "AREA-SWAMP", "activity": "gathering" },
                            { "from_hour": 16, "to_hour": 20, "zone": "AREA-MINE", "activity": "walking" },
                            { "from_hour": 20, "to_hour": 24, "zone": "AREA-HOUSES", "activity": "sleep" },
                            { "from_hour": 0, "to_hour": 8, "zone": "AREA-HOUSES", "activity": "sleep" } ] },
            { "id": "S", "name": "Static", "tier": 3, "faction": "none", "initial_trust": 0, "relationship_bias": 0.1,
              "tone_weights": { "silent": 0 },
              "schedule": [ { "from_hour": 8, "to_hour": 20, "zone": "AREA-SQUARE", "activity": "loiter" },
                            { "from_hour": 20, "to_hour": 24, "zone": "AREA-HOUSES", "activity": "sleep" },
                            { "from_hour": 0, "to_hour": 8, "zone": "AREA-HOUSES", "activity": "sleep" } ] }
          ]
        })json";
        auto V = MakeMiniVillage(Explorer, Err);
        TLS_CHECK_MSG(V != nullptr, "expanded-zone schedule loads: " + Err);
        if (V)
        {
                TLS_CHECK(V->NpcZoneAt("W", 9) == "AREA-PLAS");
                TLS_CHECK(V->NpcZoneAt("W", 14) == "AREA-SWAMP");
                TLS_CHECK(V->NpcZoneAt("W", 18) == "AREA-MINE");
        }

        // the new districts are NOT gossip zones: nobody gossips in the swamp
        {
                JsonParseResult PR = JsonParse(
                        "{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[{\"id\":\"RUM-W\","
                        "\"origin\":\"w\",\"day_created\":1,\"variants\":[\"a\"],"
                        "\"seeds\":[{\"npc\":\"S\",\"kind\":\"direct\"}]}]}");
                TLS_CHECK(PR.Ok);
                RumorSystem Sys;
                TLS_CHECK_MSG(Sys.Load(PR.Value, Err), "mini rumor data: " + Err);
                Sys.ActivateDue(1);
                Rng Rng(1);
                for (int Hour = 8; Hour <= 19; ++Hour) { Sys.TickHour(1, Hour, *V, Rng); }
                TLS_CHECK_MSG(!Sys.NpcKnows("W", "RUM-W"), "the walker never heard the rumor - the swamp is not a gossip zone");
        }
}

int main()
{
        std::printf("THE LAST SIN - M1+M2 core-logic test harness (standalone g++ build)\n");
        std::printf("same source files as the UE module: 03_Unreal/Source/TLS/Core/*\n");

        TestJson();
        TestWelshLayer();
        tls_test_rumors::RunAll();

        Game* G = MakeLoadedGame();
        if (!G)
        {
                std::printf("FATAL: data loading failed\n");
                return 2;
        }

        TestEvidenceRules(*G);
        TestVillageSim(*G);
        TestQuestAndDialogueRules(*G);
        TestRumorGameIntegration(*G);
        tls_test_quests::RunAll(*G);
        tls_test_settings::RunAll(*G);
        TestExpandedWorldZones();

        {
                Game* GSIM = MakeLoadedGame();
                if (GSIM) { TestSevenDayRumorSimulation(*GSIM); delete GSIM; }
                Game* GSAVE = MakeLoadedGame();
                if (GSAVE) { TestSaveVersionGate(*GSAVE); delete GSAVE; }
                Game* GSAVE2 = MakeLoadedGame();
                if (GSAVE2) { TestFivePointSaveLoad(*GSAVE2); delete GSAVE2; }
                Game* GCORRUPT = MakeLoadedGame();
                if (GCORRUPT) { TestCorruptSubsystemPayloads(*GCORRUPT); delete GCORRUPT; }
        }

        int Insights = 0, Collected = 0;
        tls_test_sim::RunFullPlaythrough(*G, Insights, Collected);
        tls_test_sim::RunThreePathVerification(*G);

        Game* G1 = MakeLoadedGame();
        Game* G2 = MakeLoadedGame();
        Game* G3 = MakeLoadedGame();
        if (G1 && G2 && G3)
        {
                tls_test_sim::RunSaveLoadTest(*G1, *G2, *G3);
        }

        // M3.1: the first investigation loop + its regression battery
        tls_test_investigation::RunAll();

        // M3.2: the extended loop, decay watch, order independence,
        // save/restore expansion, no-resurrection
        tls_test_m32::RunAll();
        tls_test_m37::RunAll();

        delete G; delete G1; delete G2; delete G3;
        return tls_test::ReportAndExit();
}
