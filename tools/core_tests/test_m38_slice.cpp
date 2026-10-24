// THE LAST SIN: The Sin-Eater - M3.8
// test_m38_slice: the dialogue -> case-fact testimony bridge, the accusation
// preview, and the load-time bridge validation, exercised end to end through
// the REAL game core (the same files the UE module compiles):
//
//   S1  the bridge: testimony lands through real dialogue beats, gated by the
//       testimony's OWN reveal conditions (the truth anchor is heard through
//       the bridge and still teaches nothing)
//   S2  earned confessions through the bridge: Coles' sacks account (evidence
//       granted by the choice BEFORE the revealing node), his ring at trust 35
//   S3  the shadow admission: the dialogue gate mirrors the testimony gate
//       (footprints + pattern + day 2) - without the prints the branch is shut
//   S4  the accusation board: PreviewTier == MakeAccusation tier (one
//       evaluation, two consumers), consequences land, repeat rules hold
//   S5  save v3 round-trip through bridge-learned state (byte-stable, provenance kept)
//   S6  the load-time contract: bad reveal_facts are refused before gameplay
//
// Canon note: every fact learned below arrives through the same data files
// the UE slice loads - no test-only data.

#include "tls_test_framework.h"
#include "test_fixtures.h"

#include "TLSGameState.h"
#include "TLSJson.h"

#include <memory>
#include <string>
#include <vector>

using namespace tls;

namespace tls_test_m38
{

namespace
{

// A game with EVERY data layer loaded (the M3.7 fixture shape).
Game* MakeFullGame()
{
        Game* G = MakeLoadedGame();
        if (!G) { return nullptr; }
        std::string Content, Err;

        TLS_CHECK_MSG(ReadFileToString("05_Narrative/case_facts/case_facts_slice.json", Content), "case facts file");
        JsonParseResult P = JsonParse(Content);
        TLS_CHECK_MSG(P.Ok, "case facts json: " + P.Error);
        TLS_CHECK_MSG(G->LoadCaseFactsData(P.Value, Err), "case facts load: " + Err);

        TLS_CHECK_MSG(ReadFileToString("05_Narrative/deduction/deduction_slice.json", Content), "deduction file");
        P = JsonParse(Content);
        TLS_CHECK_MSG(P.Ok, "deduction json: " + P.Error);
        TLS_CHECK_MSG(G->LoadDeductionData(P.Value, Err), "deduction load: " + Err);
        return G;
}

// Picks the first available choice whose id matches (UI-identical).
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

bool ChoiceAvailable(Game& G, const std::string& ChoiceId)
{
        std::string Err;
        std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
        for (const DialogueChoice* C : Avail)
        {
                if (C && C->Id == ChoiceId) { return true; }
        }
        (void)Err;
        return false;
}

// Full greedy sessions until the NPC's trust crosses Target.
void DriveTrustTo(Game& G, const char* DialogueId, const char* NpcId, double Target)
{
        std::string Err;
        for (int I = 0; I < 300 && G.GetTrust(NpcId) < Target - 1e-9; ++I)
        {
                if (!G.BeginDialogue(DialogueId, Err)) { return; }
                int Guard = 0;
                while (G.DialogueRunning() && Guard++ < 64)
                {
                        std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
                        if (!Avail.empty())
                        {
                                std::string Entered;
                                if (!G.PickDialogueChoice(0, Entered, Err)) { return; }
                        }
                        else
                        {
                                std::string Entered;
                                if (!G.DialogueAutoAdvance(Entered)) { return; }
                        }
                }
        }
}

} // anonymous namespace

// ---------------------------------------------------------------- sections

void RunAll()
{
        std::string Err;

        // ============================================ S1: the bridge teaches
        {
                TLS_SECTION("M3.8 S1 - testimony lands through real dialogue; the anchor still teaches nothing");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();

                // below the bridge: no testimony heard yet
                TLS_CHECK(G->Case().HeardList().empty());

                TLS_CHECK(G->BeginDialogue("DLG-GWENDOLYN-C1", Err));
                TLS_CHECK(PickChoice(*G, "G01", Err));  // ROOT -> NODE_MEMORY -> the hub
                TLS_CHECK(PickChoice(*G, "H1", Err));   // grants EVD-GWEN-LASTNIGHT, enters NODE_LASTNIGHT
                TLS_CHECK(G->EvidenceCollected("EVD-GWEN-LASTNIGHT"));

                // the reveal fired on node entry: the tray account is HEARD ...
                bool bTrayHeard = false;
                for (const HeardTestimony& H : G->Case().HeardList())
                {
                        if (H.FactId == "FACT-LAST-TRAY" && H.NpcId == "CHR-03") { bTrayHeard = true; }
                }
                TLS_CHECK_MSG(bTrayHeard, "Gwen's tray account heard through the dialogue bridge");
                // ... and the truth anchor STILL teaches nothing (pillar B: the
                // poison truth stays in the day-6 canon)
                TLS_CHECK_MSG(!G->Case().IsLearned("FACT-LAST-TRAY"),
                        "the anchor account is on the board but grants no fact");

                // the sworn list is NOT reachable below the trust-60 gate
                TLS_CHECK_MSG(!ChoiceAvailable(*G, "GU1"), "the sworn list stays shut below trust 60");
                TLS_CHECK(PickChoice(*G, "H3", Err));
                TLS_CHECK(PickChoice(*G, "H6", Err));   // ends the session

                // cross the canon threshold through real conversation
                DriveTrustTo(*G, "DLG-GWENDOLYN-C1", "CHR-03", 60.0);
                TLS_CHECK(G->GetTrust("CHR-03") >= 60.0);

                TLS_CHECK(G->BeginDialogue("DLG-GWENDOLYN-C1", Err));
                // hub order: H1 topic now spent -> the walk reaches GU1
                bool bGU1 = false;
                for (int I = 0; I < 12 && !bGU1 && G->DialogueRunning(); ++I)
                {
                        if (ChoiceAvailable(*G, "GU1")) { bGU1 = true; break; }
                        std::vector<const DialogueChoice*> Avail = G->DialogueAvailableChoices();
                        if (Avail.empty())
                        {
                                std::string Entered;
                                if (!G->DialogueAutoAdvance(Entered)) { break; }
                        }
                        else
                        {
                                std::string Entered;
                                if (!G->PickDialogueChoice(0, Entered, Err)) { break; }
                        }
                }
                TLS_CHECK_MSG(bGU1, "the sworn-list branch opens at the canon threshold");
                TLS_CHECK(PickChoice(*G, "GU1", Err));   // NODE_LIST_TOLD -> reveal fires
                TLS_CHECK_MSG(G->Case().IsLearned("FACT-17-LIST"), "the sworn list taught through dialogue");
                TLS_CHECK(G->GetFlag("FLG_GWEN_ARCHIVE_KNOWN") == 1);
                const LearnedFact* Rec = G->Case().LearnRecord("FACT-17-LIST");
                TLS_CHECK(Rec && Rec->Via == "testimony" && Rec->FromNpc == "CHR-03");
        }

        // ============================================ S2: earned confessions
        {
                TLS_SECTION("M3.8 S2 - Coles: the sacks account and the ring confession through the bridge");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                G->AdvanceSimDay();   // BH3 is a day-2 topic

                // the fraud thread: BH3 grants the evidence, NODE_FRAUD reveals the fact
                TLS_CHECK(G->BeginDialogue("DLG-COLES-C1", Err));
                TLS_CHECK(PickChoice(*G, "B1", Err));
                TLS_CHECK(PickChoice(*G, "BH1", Err));
                TLS_CHECK(PickChoice(*G, "BH3", Err));   // grants EVD-COLES-FRAUD, then NODE_FRAUD
                TLS_CHECK(G->EvidenceCollected("EVD-COLES-FRAUD"));
                TLS_CHECK_MSG(G->Case().IsLearned("FACT-NOTT-SIN"),
                        "the sacks account taught: evidence lands BEFORE the revealing node");
                const LearnedFact* Rec = G->Case().LearnRecord("FACT-NOTT-SIN");
                TLS_CHECK(Rec && Rec->Via == "testimony" && Rec->FromNpc == "CHR-13");

                // the ring confession opens only at his registry threshold (35)
                TLS_CHECK_MSG(!ChoiceAvailable(*G, "BH5"), "the ring stays shut below trust 35");
                TLS_CHECK(PickChoice(*G, "BH4", Err));
                DriveTrustTo(*G, "DLG-COLES-C1", "CHR-13", 35.0);
                TLS_CHECK(G->GetTrust("CHR-13") >= 35.0);
                TLS_CHECK(G->BeginDialogue("DLG-COLES-C1", Err));
                bool bBH5 = false;
                for (int I = 0; I < 12 && !bBH5 && G->DialogueRunning(); ++I)
                {
                        if (ChoiceAvailable(*G, "BH5")) { bBH5 = true; break; }
                        std::vector<const DialogueChoice*> Avail = G->DialogueAvailableChoices();
                        if (Avail.empty())
                        {
                                std::string Entered;
                                if (!G->DialogueAutoAdvance(Entered)) { break; }
                        }
                        else
                        {
                                std::string Entered;
                                if (!G->PickDialogueChoice(0, Entered, Err)) { break; }
                        }
                }
                TLS_CHECK_MSG(bBH5, "the confession branch opens at the canon threshold");
                TLS_CHECK(PickChoice(*G, "BH5", Err));   // NODE_RING -> reveal fires
                TLS_CHECK_MSG(G->Case().IsLearned("FACT-COLES-RING"), "the ring confession taught through dialogue");
                TLS_CHECK(G->GetFlag("FLG_COLES_RING_KNOWN") == 1);
        }

        // ============================================ S3: the shadow admission
        {
                TLS_SECTION("M3.8 S3 - Crane: the dialogue gate mirrors the testimony gate exactly");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                G->AdvanceSimDay();

                // the pattern WITHOUT the prints: the tower-night deflection
                // (CH3) opens on insight alone, but the shadow admission does not
                G->NotifyCollectEvidence("EVD-COLES-FRAUD", "the sacks account");
                G->NotifyCollectEvidence("EVD-NOTT-BODY", "the mill floor");
                G->NotifyExamineEvidence("EVD-COLES-FRAUD");
                G->NotifyExamineEvidence("EVD-NOTT-BODY");   // the board takes only what the lamp has read
                G->NotifyDrawLink("EVD-COLES-FRAUD", "EVD-NOTT-BODY");
                TLS_CHECK(G->InsightKnown("INS-PATTERN"));

                TLS_CHECK(G->BeginDialogue("DLG-CRANE-C1", Err));
                TLS_CHECK(PickChoice(*G, "C02", Err));
                TLS_CHECK_MSG(ChoiceAvailable(*G, "CH3"), "the deflection opens on insight alone");
                TLS_CHECK_MSG(!ChoiceAvailable(*G, "CH5"),
                        "the shadow admission stays shut without the physical record");
                TLS_CHECK(PickChoice(*G, "CH4", Err));
                TLS_CHECK(!G->Case().IsLearned("FACT-MILL-SHADOW"));

                // now the prints arrive - the branch opens and teaches
                G->NotifyCollectEvidence("EVD-FOOTPRINTS", "the wheel-race mud");
                TLS_CHECK(G->BeginDialogue("DLG-CRANE-C1", Err));
                TLS_CHECK(PickChoice(*G, "C02", Err));
                TLS_CHECK_MSG(ChoiceAvailable(*G, "CH5"), "prints + pattern + day 2 open the admission");
                TLS_CHECK(PickChoice(*G, "CH5", Err));   // NODE_SHADOW_TOLD -> reveal fires
                TLS_CHECK_MSG(G->Case().IsLearned("FACT-MILL-SHADOW"), "the shadow taught through dialogue");
                TLS_CHECK(G->GetFlag("FLG_MILL_SHADOW_KNOWN") == 1);
        }

        // ============================================ S4: the accusation board
        {
                TLS_SECTION("M3.8 S4 - PreviewTier never disagrees with MakeAccusation; consequences land");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                G->AdvanceSimDay();

                // an empty case: every preview is honest about weakness
                EAccusationTier Seen;
                TLS_CHECK(G->PreviewAccusationTier("ACC-SHONI-TINKER", Seen));
                TLS_CHECK_MSG(Seen == EAccusationTier::Baseless, "the county's tinker story is declared baseless");
                TLS_CHECK(G->PreviewAccusationTier("ACC-NOTT-FRAUD", Seen));
                TLS_CHECK(Seen == EAccusationTier::Baseless);
                TLS_CHECK_MSG(!G->PreviewAccusationTier("ACC-GHOST-NOBODY", Seen),
                        "unknown accusations refuse the preview");

                // build the full grounded fraud case through real play
                // (the canon INS-SINLIST route: her paper against his page)
                G->NotifyCollectEvidence("EVD-TORN-PAGE", "beneath the floor stone");
                G->NotifyExamineEvidence("EVD-TORN-PAGE");
                G->NotifyCollectEvidence("EVD-RITE-PAPER", "the shelf above the hearth");
                G->NotifyCollectEvidence("EVD-GWEN-GUINEA", "Gwendolyn's admission");
                G->NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "the mill scale-board");
                G->NotifyExamineEvidence("EVD-RITE-PAPER");
                G->NotifyExamineEvidence("EVD-GWEN-GUINEA");
                G->NotifyDrawLink("EVD-RITE-PAPER", "EVD-GWEN-GUINEA");
                TLS_CHECK(G->InsightKnown("INS-SINLIST"));
                TLS_CHECK(G->EvidenceCollected("EVD-SINLIST"));   // granted by the insight
                TLS_CHECK(G->PreviewAccusationTier("ACC-NOTT-FRAUD", Seen));
                TLS_CHECK_MSG(Seen == EAccusationTier::Grounded,
                        "the full bundle grounds the fraud accusation");

                // the intent-crime cap: with the pattern AND his sermon heard,
                // Crane's tier still lands partial - the data refuses to prove
                // intent inside this slice (canon: the real confrontation is C6)
                G->NotifyCollectEvidence("EVD-COLES-FRAUD", "the sacks account");
                G->NotifyCollectEvidence("EVD-NOTT-BODY", "the mill floor");
                G->NotifyExamineEvidence("EVD-COLES-FRAUD");
                G->NotifyExamineEvidence("EVD-NOTT-BODY");
                G->NotifyDrawLink("EVD-COLES-FRAUD", "EVD-NOTT-BODY");   // INS-PATTERN
                G->NotifyCollectEvidence("EVD-CRANE-SERMON", "the sermon, written down");
                G->NotifyExamineEvidence("EVD-CRANE-SERMON");
                TLS_CHECK(G->InsightKnown("INS-PATTERN"));
                EAccusationTier Capped;
                TLS_CHECK(G->PreviewAccusationTier("ACC-CRANE-SERMON", Capped));
                TLS_CHECK_MSG(Capped == EAccusationTier::Partial,
                        "intent crimes stay partial - the data caps the tier");

                // the preview is a READ: previewing again changes nothing and
                // records nothing
                EAccusationTier Again;
                TLS_CHECK(G->PreviewAccusationTier("ACC-NOTT-FRAUD", Again));
                TLS_CHECK_MSG(Again == EAccusationTier::Grounded, "the grounded case keeps its tier");
                TLS_CHECK(!G->Deduction().AccusedBefore("ACC-NOTT-FRAUD"));

                // speak it: the tier is exactly what the preview said
                EAccusationTier Tier;
                TLS_CHECK(G->MakeAccusation("ACC-NOTT-FRAUD", Tier, Err));
                TLS_CHECK_MSG(Tier == EAccusationTier::Grounded, "the spoken tier equals the preview");
                TLS_CHECK(G->GetFlag("FLG_NOTT_SIN_PUBLIC") == 1);
                TLS_CHECK(G->Deduction().AccusedBefore("ACC-NOTT-FRAUD"));
                TLS_CHECK(!G->MakeAccusation("ACC-NOTT-FRAUD", Tier, Err));   // not repeatable

                // the baseless words still land, and cost the speaker nothing structural
                TLS_CHECK(G->MakeAccusation("ACC-SHONI-TINKER", Tier, Err));
                TLS_CHECK(Tier == EAccusationTier::Baseless);
        }

        // ============================================ S5: save through the bridge
        {
                TLS_SECTION("M3.8 S5 - the bridge-learned state survives the seam byte-stably");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                G->AdvanceSimDay();

                TLS_CHECK(G->BeginDialogue("DLG-COLES-C1", Err));
                TLS_CHECK(PickChoice(*G, "B1", Err));
                TLS_CHECK(PickChoice(*G, "BH3", Err));
                TLS_CHECK(G->Case().IsLearned("FACT-NOTT-SIN"));

                const std::string S = G->SaveToString();
                std::unique_ptr<Game> G2(MakeFullGame());
                G2->NewGame();
                TLS_CHECK_MSG(G2->LoadFromString(S, Err), "v3 payload with bridge state loads: " + Err);
                TLS_CHECK(G2->SaveToString() == S);   // byte-identical resave
                TLS_CHECK(G2->Case().IsLearned("FACT-NOTT-SIN"));
                const LearnedFact* Rec = G2->Case().LearnRecord("FACT-NOTT-SIN");
                TLS_CHECK(Rec && Rec->Via == "testimony" && Rec->FromNpc == "CHR-13");
                bool bFraudHeard = false;
                for (const HeardTestimony& H : G2->Case().HeardList())
                {
                        if (H.FactId == "FACT-NOTT-SIN" && H.NpcId == "CHR-13") { bFraudHeard = true; }
                }
                TLS_CHECK(bFraudHeard);
        }

        // ============================================ S6: the load-time contract
        {
                TLS_SECTION("M3.8 S6 - bad reveal_facts are refused before gameplay");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                TLS_CHECK_MSG(G->ValidateDialogueCaseLinks(Err), "the shipped data passes its own contract");

                // a dialogue that reveals a fact which does not exist
                {
                        std::unique_ptr<Game> GBad(MakeFullGame());
                        GBad->NewGame();
                        const char* Bad =
                                "{\"schema\":\"tls.dialogue.v1\",\"id\":\"DLG-BAD-1\",\"npc\":\"CHR-13\",\"root\":\"R\","
                                "\"nodes\":[{\"id\":\"R\",\"speaker\":\"CHR-13\",\"text\":\"...\","
                                "\"on_enter\":{\"reveal_facts\":[\"FACT-DOES-NOT-EXIST\"]}}]}";
                        JsonParseResult P = JsonParse(Bad);
                        TLS_CHECK(P.Ok);
                        TLS_CHECK(GBad->LoadDialogueData(P.Value, Err));
                        TLS_CHECK_MSG(!GBad->ValidateDialogueCaseLinks(Err), "unknown fact refused");
                        TLS_CHECK_MSG(Err.find("unknown fact") != std::string::npos, "the error names the fault");
                }
                // a dialogue whose speaker owns no testimony for the fact
                {
                        std::unique_ptr<Game> GBad(MakeFullGame());
                        GBad->NewGame();
                        const char* Bad =
                                "{\"schema\":\"tls.dialogue.v1\",\"id\":\"DLG-BAD-2\",\"npc\":\"CHR-13\",\"root\":\"R\","
                                "\"nodes\":[{\"id\":\"R\",\"speaker\":\"CHR-13\",\"text\":\"...\","
                                "\"on_enter\":{\"reveal_facts\":[\"FACT-17-LIST\"]}}]}";
                        JsonParseResult P = JsonParse(Bad);
                        TLS_CHECK(P.Ok);
                        TLS_CHECK(GBad->LoadDialogueData(P.Value, Err));
                        TLS_CHECK_MSG(!GBad->ValidateDialogueCaseLinks(Err), "wrong-owner reveal refused");
                        TLS_CHECK_MSG(Err.find("owns no testimony") != std::string::npos, "the error names the fault");
                }
                // a session without the case layer passes trivially (legacy shape)
                {
                        std::unique_ptr<Game> Legacy(MakeLoadedGame());
                        TLS_CHECK(Legacy != nullptr);
                        if (Legacy)
                        {
                                Legacy->NewGame();
                                TLS_CHECK_MSG(Legacy->ValidateDialogueCaseLinks(Err), "legacy sessions are valid by definition");
                        }
                }
        }
}

} // namespace tls_test_m38
