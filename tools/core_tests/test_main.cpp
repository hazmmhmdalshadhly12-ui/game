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
#include <string>

using namespace tls;

namespace
{

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

} // anonymous namespace

int main()
{
        std::printf("THE LAST SIN - M1 core-logic test harness (standalone g++ build)\n");
        std::printf("same source files as the UE module: 03_Unreal/Source/TLS/Core/*\n");

        TestJson();
        TestWelshLayer();

        Game* G = MakeLoadedGame();
        if (!G)
        {
                std::printf("FATAL: data loading failed\n");
                return 2;
        }

        TestEvidenceRules(*G);
        TestVillageSim(*G);
        TestQuestAndDialogueRules(*G);

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

        delete G; delete G1; delete G2; delete G3;
        return tls_test::ReportAndExit();
}
