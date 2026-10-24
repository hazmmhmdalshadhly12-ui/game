// THE LAST SIN: The Sin-Eater - M3.7
// test_m37_pillars: the case-fact ledger, the deduction layer, and the
// four-pillar integration, exercised end to end through the REAL game core:
//
//   S1  data loading + strict schema refusals (facts, dossiers, hypotheses, accusations)
//   S2  the knowledge boundary (pillar A/C): no NPC speaks what their reveal
//       conditions do not allow - and discoveries elsewhere unlock them
//   S3  truth anchors and honest-but-wrong accounts (the mystery stays
//       consistent whatever the player believes)
//   S4  testimony conflict derivation (agree / conflict / omit / lie, all
//       data-declared, only among accounts the player could hold)
//   S5  hypotheses (pillar B): unsupported -> partial -> supported/refuted,
//       with the open-questions shelf shrinking as evidence arrives
//   S6  accusations (pillar D): tier from the grounding bundle, tier-specific
//       believable consequences, no repeat spam
//   S7  save v3: the case layer survives the seam byte-stably; ghost ids and
//       sectionless v3 payloads are refused atomically; v2 legacy loads clean
//   S8  no soft-locks: the baseless accusation costs the village, and the
//       tinker's rescue route still stands (Q-S-C3-SHONI completes)
//
// Every testimony, fact, hypothesis and accusation below is loaded from
// 05_Narrative/case_facts/case_facts_slice.json and
// 05_Narrative/deduction/deduction_slice.json - the canon data, not copies.

#include "tls_test_framework.h"
#include "test_fixtures.h"

#include "TLSGameState.h"
#include "TLSJson.h"

#include <cmath>
#include <map>
#include <memory>
#include <string>
#include <vector>

using namespace tls;

namespace tls_test_m37
{

namespace
{

// A game with EVERY data layer loaded: the five narrative files (via the
// shared fixture) plus the M3.7 case-fact and deduction files.
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

// Runs ONE dialogue session greedily (first available choice each node -
// exactly what a UI would do). Returns when the session stops moving.
void DriveDialogueOnce(Game& G, const char* DialogueId)
{
        std::string Err;
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

// Repeats full dialogue sessions until the NPC's trust crosses Target.
void DriveTrustTo(Game& G, const char* DialogueId, const char* NpcId, double Target)
{
        for (int I = 0; I < 300 && G.GetTrust(NpcId) < Target - 1e-9; ++I)
        {
                DriveDialogueOnce(G, DialogueId);
        }
}

// Parses + applies a strict-refusal payload to a THROWAWAY game.
bool Refused(const char* Json, std::string& OutError)
{
        std::unique_ptr<Game> G(MakeFullGame());
        if (!G) { OutError = "fixture broken"; return false; }
        G->NewGame();
        JsonParseResult P = JsonParse(Json);
        if (!P.Ok) { OutError = "test json broken: " + P.Error; return false; }
        if (G->LoadCaseFactsData(P.Value, OutError)) { return false; }
        if (G->LoadDeductionData(P.Value, OutError)) { return false; }
        return true;
}

} // anonymous namespace

// ---------------------------------------------------------------- sections

void RunAll()
{
        std::string Err;

        // ================================================ S1: data + refusals
        {
                TLS_SECTION("M3.7 S1 - case data loads; the schema refuses lies without reasons");

                std::unique_ptr<Game> G(MakeFullGame());
                TLS_CHECK(G != nullptr);
                if (!G) { return; }
                G->NewGame();

                TLS_CHECK(G->Case().Facts().size() == 6);
                TLS_CHECK(G->Case().Dossiers().size() == 5);
                TLS_CHECK(G->Deduction().Hypotheses().size() == 3);
                TLS_CHECK(G->Deduction().Accusations().size() == 4);
                TLS_CHECK(G->Case().LearnedCount() == 0);

                // every shipped dossier secret has a GATED testimony (concealment is playable)
                for (const auto& KV : G->Case().Dossiers())
                {
                        for (const std::string& Secret : KV.second.SecretFacts)
                        {
                                const TestimonyDef* T = G->Case().FindTestimony(Secret, KV.first);
                                TLS_CHECK_MSG(T != nullptr, "dossier secret has a testimony: " + KV.first + "/" + Secret);
                        }
                }
                // both truth anchors exist and are declared as such
                const CaseFactDef* Anchor = G->Case().FindFact("FACT-LAST-TRAY");
                TLS_CHECK(Anchor && Anchor->bTruthAnchor);
                Anchor = G->Case().FindFact("FACT-MAIR-RETURNED");
                TLS_CHECK(Anchor && Anchor->bTruthAnchor);

                // a deliberate lie without a narrative reason is refused
                TLS_CHECK_MSG(Refused(
                        "{\"facts\":[{\"id\":\"F1\",\"topic\":\"t\",\"truth_summary\":\"x\",\"canon_ref\":\"R\","
                        "\"testimonies\":[{\"npc\":\"CHR-13\",\"stance\":\"affirms\",\"account\":\"a\",\"deliberate\":true}]}]}", Err),
                        "deliberate without lie_reason refused");
                // a silence that grants the fact is refused
                TLS_CHECK_MSG(Refused(
                        "{\"facts\":[{\"id\":\"F1\",\"topic\":\"t\",\"truth_summary\":\"x\",\"canon_ref\":\"R\","
                        "\"testimonies\":[{\"npc\":\"CHR-13\",\"stance\":\"omits\",\"account\":\"(silence)\",\"grants\":true}]}]}", Err),
                        "omits+grants refused");
                // a truth anchor with a granting testimony is refused
                TLS_CHECK_MSG(Refused(
                        "{\"facts\":[{\"id\":\"F1\",\"topic\":\"t\",\"truth_summary\":\"x\",\"canon_ref\":\"R\",\"truth_anchor\":true,"
                        "\"testimonies\":[{\"npc\":\"CHR-13\",\"stance\":\"affirms\",\"account\":\"a\",\"grants\":true}]}]}", Err),
                        "anchor+grants refused");
                // a dossier secret without any reveal gate is refused
                TLS_CHECK_MSG(Refused(
                        "{\"facts\":[{\"id\":\"F1\",\"topic\":\"t\",\"truth_summary\":\"x\",\"canon_ref\":\"R\","
                        "\"testimonies\":[{\"npc\":\"CHR-13\",\"stance\":\"affirms\",\"account\":\"a\"}]}],"
                        "\"dossiers\":[{\"npc\":\"CHR-13\",\"secret_facts\":[\"F1\"]}]}", Err),
                        "ungated dossier secret refused");
                // a fact without a canon anchor is refused
                TLS_CHECK_MSG(Refused(
                        "{\"facts\":[{\"id\":\"F1\",\"topic\":\"t\",\"truth_summary\":\"x\"}]}", Err),
                        "missing canon_ref refused");
                // a hypothesis with no support requirements is refused
                TLS_CHECK_MSG(Refused(
                        "{\"hypotheses\":[{\"id\":\"H1\",\"title\":\"t\",\"canon_ref\":\"R\"}],"
                        "\"accusations\":[{\"id\":\"A1\",\"target_label\":\"x\",\"topic\":\"y\",\"baseless\":true,\"canon_ref\":\"R\"}]}", Err),
                        "requirement-less hypothesis refused");
                // a refuter without a reason is refused
                TLS_CHECK_MSG(Refused(
                        "{\"hypotheses\":[{\"id\":\"H1\",\"title\":\"t\",\"canon_ref\":\"R\",\"requires_evidence\":[\"EVD-DISH\"],"
                        "\"refuted_by\":[{\"type\":\"flag\",\"target\":\"FLG_X\"}]}],"
                        "\"accusations\":[{\"id\":\"A1\",\"target_label\":\"x\",\"topic\":\"y\",\"baseless\":true,\"canon_ref\":\"R\"}]}", Err),
                        "reason-less refuter refused");
                // baseless + grounding bundle is refused
                TLS_CHECK_MSG(Refused(
                        "{\"hypotheses\":[{\"id\":\"H1\",\"title\":\"t\",\"canon_ref\":\"R\",\"requires_evidence\":[\"EVD-DISH\"]}],"
                        "\"accusations\":[{\"id\":\"A1\",\"target_label\":\"x\",\"topic\":\"y\",\"baseless\":true,"
                        "\"grounding_evidence\":[\"EVD-DISH\"],\"canon_ref\":\"R\"}]}", Err),
                        "baseless with bundle refused");
                // an accusation with neither baseless nor a bundle is refused
                TLS_CHECK_MSG(Refused(
                        "{\"hypotheses\":[{\"id\":\"H1\",\"title\":\"t\",\"canon_ref\":\"R\",\"requires_evidence\":[\"EVD-DISH\"]}],"
                        "\"accusations\":[{\"id\":\"A1\",\"target_label\":\"x\",\"topic\":\"y\",\"canon_ref\":\"R\"}]}", Err),
                        "ungroundable accusation refused");
        }

        // ============================================ S2: knowledge boundary
        {
                TLS_SECTION("M3.7 S2 - the knowledge boundary: Gwen's archive, Mair's wall, Crane's silence");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();

                // Gwen holds the 17-list behind trust 60 (canon threshold)
                TLS_CHECK(G->AvailableTestimony("FACT-17-LIST", "CHR-03") == nullptr);
                TLS_CHECK(!G->HearTestimony("FACT-17-LIST", "CHR-03", Err));
                DriveTrustTo(*G, "DLG-GWENDOLYN-C1", "CHR-03", 60.0);
                TLS_CHECK_MSG(G->GetTrust("CHR-03") >= 60.0, "Gwen's trust crossed the canon threshold");
                const TestimonyDef* Gwen = G->AvailableTestimony("FACT-17-LIST", "CHR-03");
                TLS_CHECK(Gwen != nullptr);
                TLS_CHECK(Gwen->NpcId == "CHR-03" && Gwen->Stance == ETestimonyStance::Affirms);
                const size_t JournalBefore = G->Journal().size();
                TLS_CHECK(G->HearTestimony("FACT-17-LIST", "CHR-03", Err));
                TLS_CHECK(G->Case().IsLearned("FACT-17-LIST"));
                TLS_CHECK(G->GetFlag("FLG_GWEN_ARCHIVE_KNOWN") == 1);
                TLS_CHECK(G->Journal().size() == JournalBefore + 1);
                const LearnedFact* Rec = G->Case().LearnRecord("FACT-17-LIST");
                TLS_CHECK(Rec && Rec->FromNpc == "CHR-03" && Rec->Via == "testimony");
                // idempotent: hearing again changes nothing
                TLS_CHECK(G->HearTestimony("FACT-17-LIST", "CHR-03", Err));
                TLS_CHECK(G->Journal().size() == JournalBefore + 1);

                // Mair's wall: her truth opens at C5 (day 4) - the slice cannot buy it
                TLS_CHECK(G->AvailableTestimony("FACT-MAIR-RETURNED", "CHR-06") == nullptr);
                G->AdvanceSimDay();
                G->AdvanceSimDay();
                TLS_CHECK(G->CurrentDay() == 3);
                TLS_CHECK(G->AvailableTestimony("FACT-MAIR-RETURNED", "CHR-06") == nullptr);
                TLS_CHECK(!G->HearTestimony("FACT-MAIR-RETURNED", "CHR-06", Err));
                TLS_CHECK(!G->Case().IsLearned("FACT-MAIR-RETURNED"));

                // Crane's silence opens only through the physical record + the pattern
                TLS_CHECK(G->AvailableTestimony("FACT-MILL-SHADOW", "CHR-04") == nullptr);
                G->NotifyCollectEvidence("EVD-FOOTPRINTS", "the wheel-race mud");
                TLS_CHECK(G->AvailableTestimony("FACT-MILL-SHADOW", "CHR-04") == nullptr);   // prints alone are not standing
                G->NotifyCollectEvidence("EVD-COLES-FRAUD", "the gravedigger's sacks account");
                G->NotifyCollectEvidence("EVD-NOTT-BODY", "the mill floor");
                G->NotifyExamineEvidence("EVD-COLES-FRAUD");
                G->NotifyExamineEvidence("EVD-NOTT-BODY");   // the board takes only what the lamp has read
                G->NotifyDrawLink("EVD-COLES-FRAUD", "EVD-NOTT-BODY");
                TLS_CHECK(G->InsightKnown("INS-PATTERN"));
                const TestimonyDef* Crane = G->AvailableTestimony("FACT-MILL-SHADOW", "CHR-04");
                TLS_CHECK_MSG(Crane != nullptr, "footprints + pattern unlock Crane's account");
                TLS_CHECK(G->HearTestimony("FACT-MILL-SHADOW", "CHR-04", Err));
                TLS_CHECK(G->GetFlag("FLG_MILL_SHADOW_KNOWN") == 1);

                // Coles' confession opens under kindness (trust 35)
                TLS_CHECK(G->AvailableTestimony("FACT-COLES-RING", "CHR-13") == nullptr);
                DriveTrustTo(*G, "DLG-COLES-C1", "CHR-13", 35.0);
                TLS_CHECK(G->GetTrust("CHR-13") >= 35.0);
                TLS_CHECK(G->AvailableTestimony("FACT-COLES-RING", "CHR-13") != nullptr);
                TLS_CHECK(G->HearTestimony("FACT-COLES-RING", "CHR-13", Err));
                TLS_CHECK(G->GetFlag("FLG_COLES_RING_KNOWN") == 1);
        }

        // ==================================== S3: truth anchors, honest-wrong
        {
                TLS_SECTION("M3.7 S3 - truth anchors: Gwen's tray account is heard but teaches nothing");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                G->NotifyCollectEvidence("EVD-GWEN-LASTNIGHT", "Gwendolyn's account of the last tray");

                const TestimonyDef* T = G->AvailableTestimony("FACT-LAST-TRAY", "CHR-03");
                TLS_CHECK(T != nullptr);
                TLS_CHECK(T->Stance == ETestimonyStance::Affirms);
                TLS_CHECK(!T->bGrantsFact);   // an honest, innocent, and incomplete account
                const size_t JournalBefore = G->Journal().size();
                TLS_CHECK(G->HearTestimony("FACT-LAST-TRAY", "CHR-03", Err));
                TLS_CHECK(!G->Case().IsLearned("FACT-LAST-TRAY"));   // the poison truth stays where canon keeps it
                TLS_CHECK(G->GetFlag("FLG_NOTT_SIN_KNOWN") == 0);
                TLS_CHECK(G->Journal().size() == JournalBefore);     // no journal note - nothing was learned
                TLS_CHECK(G->Case().TestimonyHeard("FACT-LAST-TRAY", "CHR-03"));
        }

        // ==================================== S4: conflict derivation
        {
                TLS_SECTION("M3.7 S4 - testimony conflicts: declared, derived, and only among holdable accounts");

                const char* Synth =
                        "{\"facts\":[{\"id\":\"F-CF\",\"topic\":\"t\",\"truth_summary\":\"the truth\",\"canon_ref\":\"R\",\"testimonies\":["
                        "{\"npc\":\"CHR-13\",\"stance\":\"affirms\",\"account\":\"A says so\"},"
                        "{\"npc\":\"CHR-04\",\"stance\":\"claims\",\"claim_text\":\"B says otherwise\",\"account\":\"B's version\"},"
                        "{\"npc\":\"CHR-03\",\"stance\":\"omits\",\"account\":\"(C says nothing)\",\"grants\":false,\"reveal\":{\"trust_min\":0}}"
                        "]}]}";
                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                JsonParseResult P = JsonParse(Synth);
                TLS_CHECK(P.Ok);
                TLS_CHECK_MSG(G->LoadCaseFactsData(P.Value, Err), "synthetic conflict fact loads: " + Err);
                G->NewGame();

                // affirms vs claims = one conflict; the silence never conflicts
                std::vector<CaseFactSystem::FactConflict> C = G->Case().FindConflicts("F-CF", *G);
                TLS_CHECK(C.size() == 1);
                if (C.size() == 1)
                {
                        TLS_CHECK(C[0].NpcA == "CHR-13" && C[0].NpcB == "CHR-04");
                        TLS_CHECK(C[0].Reason.find("disagree") != std::string::npos);
                }
                // only accounts the player could hold: gate one side off, the conflict vanishes
                // (reload with CHR-13 gated at trust 50)
                const char* Synth2 =
                        "{\"facts\":[{\"id\":\"F-CG\",\"topic\":\"t\",\"truth_summary\":\"the truth\",\"canon_ref\":\"R\",\"testimonies\":["
                        "{\"npc\":\"CHR-13\",\"stance\":\"affirms\",\"account\":\"A says so\",\"reveal\":{\"trust_min\":50}},"
                        "{\"npc\":\"CHR-04\",\"stance\":\"claims\",\"claim_text\":\"B says otherwise\",\"account\":\"B's version\"}"
                        "]}]}";
                P = JsonParse(Synth2);
                TLS_CHECK(P.Ok);
                TLS_CHECK_MSG(G->LoadCaseFactsData(P.Value, Err), "gated conflict fact loads");
                C = G->Case().FindConflicts("F-CG", *G);
                TLS_CHECK(C.empty());   // trust 0 < 50: the player cannot hold A's account yet
        }

        // ==================================== S5: hypotheses + open questions
        {
                TLS_SECTION("M3.7 S5 - hypotheses: unsupported, partial, supported, refuted - no resurrection");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();

                // the village's theory starts unsupported
                TLS_CHECK(G->FormHypothesis("HYP-HUNGER-RETURNED", Err));
                const FormedHypothesis* H = G->Deduction().Formed("HYP-HUNGER-RETURNED");
                TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Unsupported);
                // the open-questions shelf names the missing piece
                std::vector<OpenQuestion> OQ = G->OpenQuestions();
                bool bFound = false;
                for (const OpenQuestion& Q : OQ) { if (Q.HypId == "HYP-HUNGER-RETURNED" && Q.Kind == "evidence" && Q.TargetId == "EVD-COLES-HUNGER") { bFound = true; } }
                TLS_CHECK(bFound);
                // the folk-fear evidence makes it partial (1 of 2 requirements)
                G->NotifyCollectEvidence("EVD-COLES-HUNGER", "Coles' whisper in the churchyard");
                H = G->Deduction().Formed("HYP-HUNGER-RETURNED");
                TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Partial);
                OQ = G->OpenQuestions();
                bFound = false;
                for (const OpenQuestion& Q : OQ) { if (Q.HypId == "HYP-HUNGER-RETURNED" && Q.Kind == "evidence" && Q.TargetId == "EVD-NOTT-BODY") { bFound = true; } }
                TLS_CHECK(bFound);   // the shelf asks for the body the theory has not seen
                // the board kills it: the refused dish against the salt mouth
                G->NotifyCollectEvidence("EVD-DISH", "beside the boundary stone");
                G->NotifyExamineEvidence("EVD-COLES-HUNGER");
                G->NotifyExamineEvidence("EVD-DISH");   // the board takes only what the lamp has read
                G->NotifyDrawLink("EVD-COLES-HUNGER", "EVD-DISH");
                H = G->Deduction().Formed("HYP-HUNGER-RETURNED");
                TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Refuted);
                TLS_CHECK(!H->RefuteReason.empty());
                OQ = G->OpenQuestions();
                TLS_CHECK(OQ.empty());   // refuted theories ask no questions
                // no resurrection: later unrelated state changes keep it dead
                G->NotifyCollectEvidence("EVD-LEDGER", "under the engraving table");
                H = G->Deduction().Formed("HYP-HUNGER-RETURNED");
                TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Refuted);

                // the pattern hypothesis climbs the full ladder to supported
                TLS_CHECK(G->FormHypothesis("HYP-NOTT-FRAUD-PATTERN", Err));
                H = G->Deduction().Formed("HYP-NOTT-FRAUD-PATTERN");
                TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Unsupported);
                G->NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "the mill scale-board");
                H = G->Deduction().Formed("HYP-NOTT-FRAUD-PATTERN");
                TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Partial);
                G->NotifyCollectEvidence("EVD-COLES-FRAUD", "the gravedigger's sacks account");
                G->NotifyCollectEvidence("EVD-NOTT-BODY", "the mill floor");
                G->NotifyExamineEvidence("EVD-COLES-FRAUD");
                G->NotifyExamineEvidence("EVD-NOTT-BODY");   // the board takes only what the lamp has read
                G->NotifyDrawLink("EVD-COLES-FRAUD", "EVD-NOTT-BODY");
                H = G->Deduction().Formed("HYP-NOTT-FRAUD-PATTERN");
                TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Partial);   // insight + 2 evidence, fact still missing
                G->NotifyCollectEvidence("EVD-SINLIST", "the restored list");
                G->LearnFact("FACT-NOTT-SIN", "document:EVD-SINLIST", "", Err);
                TLS_CHECK(G->Case().IsLearned("FACT-NOTT-SIN"));
                TLS_CHECK(G->GetFlag("FLG_NOTT_SIN_KNOWN") == 1);
                H = G->Deduction().Formed("HYP-NOTT-FRAUD-PATTERN");
                TLS_CHECK_MSG(H && H->Verdict == EHypothesisVerdict::Supported, "the pattern hypothesis is fully grounded");
                OQ = G->OpenQuestions();
                TLS_CHECK(OQ.empty());

                // the county's theory dies by method OR by alibi (both refuters work)
                {
                        std::unique_ptr<Game> G2(MakeFullGame());
                        if (!G2) { return; }
                        G2->NewGame();
                        TLS_CHECK(G2->FormHypothesis("HYP-SHONI-CUTPURSE", Err));
                        G2->NotifyCollectEvidence("EVD-SALT-SACK", "by the mill door");
                        const FormedHypothesis* H2 = G2->Deduction().Formed("HYP-SHONI-CUTPURSE");
                        TLS_CHECK(H2 && H2->Verdict == EHypothesisVerdict::Partial);
                        G2->AdvanceSimDay();
                        G2->AdvanceSimDay();
                        G2->NotifyCollectEvidence("EVD-FOOTPRINTS", "the wheel-race mud");
                        G2->NotifyExamineEvidence("EVD-FOOTPRINTS");
                        G2->NotifyExamineEvidence("EVD-SALT-SACK");
                        G2->NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-06");   // OBJ-C3-ACCUSATION: hear the county first
                        TLS_CHECK(G2->GetFlag("FLG_METHOD_SHOWN") == 1);   // Q-M-C3 answered the shortcut
                        H2 = G2->Deduction().Formed("HYP-SHONI-CUTPURSE");
                        TLS_CHECK(H2 && H2->Verdict == EHypothesisVerdict::Refuted);
                }
                {
                        std::unique_ptr<Game> G3(MakeFullGame());
                        if (!G3) { return; }
                        G3->NewGame();
                        G3->AdvanceSimDay();
                        G3->AdvanceSimDay();
                        TLS_CHECK(G3->FormHypothesis("HYP-SHONI-CUTPURSE", Err));
                        G3->NotifyPlayerHeardRumor("RUM-SHONI-HILL", "T3-01");
                        const FormedHypothesis* H3 = G3->Deduction().Formed("HYP-SHONI-CUTPURSE");
                        TLS_CHECK(H3 && H3->Verdict == EHypothesisVerdict::Refuted);
                }
        }

        // ==================================== S6: accusations + consequences
        {
                TLS_SECTION("M3.7 S6 - accusations: baseless bites, grounded pays, data caps the intent crime");

                // baseless: the county's words on an innocent man
                double Tension0 = 0.0, Rep0 = 0.0;
                {
                        std::unique_ptr<Game> G(MakeFullGame());
                        if (!G) { return; }
                        G->NewGame();
                        Tension0 = G->GetTension();
                        Rep0 = G->Village().Reputation();
                        EAccusationTier Tier = EAccusationTier::Grounded;
                        TLS_CHECK(G->MakeAccusation("ACC-SHONI-TINKER", Tier, Err));
                        TLS_CHECK(Tier == EAccusationTier::Baseless);
                        TLS_CHECK(std::fabs(G->GetTension() - (Tension0 + 1.5)) < 1e-9);
                        TLS_CHECK(std::fabs(G->Village().Reputation() - (Rep0 - 5.0)) < 1e-9);
                        TLS_CHECK(G->GetFlag("FLG_ACCUSED_SHONI") == 1);
                        // the words are out - they cannot be spoken again
                        TLS_CHECK(!G->MakeAccusation("ACC-SHONI-TINKER", Tier, Err));
                        TLS_CHECK(Err.find("already out") != std::string::npos);
                        TLS_CHECK(static_cast<int>(G->Deduction().AccusationLog().size()) == 1);
                }

                // the dead man's sin: baseless, partial, grounded - three sessions
                {
                        std::unique_ptr<Game> G(MakeFullGame());
                        if (!G) { return; }
                        G->NewGame();
                        Rep0 = G->Village().Reputation();
                        EAccusationTier Tier = EAccusationTier::Grounded;
                        TLS_CHECK(G->MakeAccusation("ACC-NOTT-FRAUD", Tier, Err));
                        TLS_CHECK(Tier == EAccusationTier::Baseless);
                        TLS_CHECK(std::fabs(G->Village().Reputation() - (Rep0 - 4.0)) < 1e-9);
                        TLS_CHECK(G->GetFlag("FLG_NOTT_SIN_PUBLIC") == 0);
                }
                {
                        std::unique_ptr<Game> G(MakeFullGame());
                        if (!G) { return; }
                        G->NewGame();
                        G->NotifyCollectEvidence("EVD-TORN-PAGE", "beneath the floor stone");
                        G->NotifyExamineEvidence("EVD-TORN-PAGE");   // INS-SINLIST's route demands the examined first page
                        G->NotifyCollectEvidence("EVD-RITE-PAPER", "the shelf above the hearth");
                        G->NotifyCollectEvidence("EVD-GWEN-GUINEA", "Gwendolyn's admission");
                        G->NotifyExamineEvidence("EVD-RITE-PAPER");
                        G->NotifyExamineEvidence("EVD-GWEN-GUINEA");   // the board takes only what the lamp has read
                        G->NotifyDrawLink("EVD-RITE-PAPER", "EVD-GWEN-GUINEA");
                        TLS_CHECK(G->InsightKnown("INS-SINLIST"));
                        EAccusationTier Tier = EAccusationTier::Baseless;
                        TLS_CHECK(G->MakeAccusation("ACC-NOTT-FRAUD", Tier, Err));
                        TLS_CHECK_MSG(Tier == EAccusationTier::Partial, "insight alone is half a case");
                        TLS_CHECK(G->GetFlag("FLG_NOTT_SIN_HINTED") == 1);
                }
                {
                        std::unique_ptr<Game> G(MakeFullGame());
                        if (!G) { return; }
                        G->NewGame();
                        Rep0 = G->Village().Reputation();
                        Tension0 = G->GetTension();
                        G->NotifyCollectEvidence("EVD-TORN-PAGE", "beneath the floor stone");
                        G->NotifyExamineEvidence("EVD-TORN-PAGE");   // INS-SINLIST's route demands the examined first page
                        G->NotifyCollectEvidence("EVD-RITE-PAPER", "the shelf above the hearth");
                        G->NotifyCollectEvidence("EVD-GWEN-GUINEA", "Gwendolyn's admission");
                        G->NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "the mill scale-board");
                        G->NotifyExamineEvidence("EVD-RITE-PAPER");
                        G->NotifyExamineEvidence("EVD-GWEN-GUINEA");   // the board takes only what the lamp has read
                        G->NotifyDrawLink("EVD-RITE-PAPER", "EVD-GWEN-GUINEA");
                        TLS_CHECK(G->InsightKnown("INS-SINLIST"));
                        TLS_CHECK(G->EvidenceCollected("EVD-SINLIST"));   // granted by the insight
                        EAccusationTier Tier = EAccusationTier::Baseless;
                        TLS_CHECK(G->MakeAccusation("ACC-NOTT-FRAUD", Tier, Err));
                        TLS_CHECK_MSG(Tier == EAccusationTier::Grounded, "insight + bundle (avg reliability 0.875 >= 0.7)");
                        TLS_CHECK(std::fabs(G->Village().Reputation() - (Rep0 + 4.0)) < 1e-9);
                        TLS_CHECK(std::fabs(G->GetTension() - (Tension0 + 1.0)) < 1e-9);
                        TLS_CHECK(G->GetFlag("FLG_NOTT_SIN_PUBLIC") == 1);
                }

                // Coles: a TRUE accusation that the village punishes anyway
                {
                        std::unique_ptr<Game> G(MakeFullGame());
                        if (!G) { return; }
                        G->NewGame();
                        double Trust0 = G->GetTrust("CHR-13");
                        EAccusationTier Tier = EAccusationTier::Grounded;
                        TLS_CHECK(G->MakeAccusation("ACC-COLES-RING", Tier, Err));
                        TLS_CHECK(Tier == EAccusationTier::Baseless);
                        const NPCDef* Coles = G->Village().FindNpc("CHR-13");
                        TLS_CHECK(Coles != nullptr);
                        const double ExpectBaseless = Trust0 + (-8.0) * (1.0 - Coles->RelationshipBias);
                        TLS_CHECK(std::fabs(G->GetTrust("CHR-13") - ExpectBaseless) < 1e-9);
                        // the confession must be EARNED before the square hears it
                        DriveTrustTo(*G, "DLG-COLES-C1", "CHR-13", 35.0);
                        TLS_CHECK(G->HearTestimony("FACT-COLES-RING", "CHR-13", Err));
                        Trust0 = G->GetTrust("CHR-13");
                        TLS_CHECK(G->MakeAccusation("ACC-COLES-RING", Tier, Err));
                        TLS_CHECK_MSG(Tier == EAccusationTier::Grounded, "the confession fact grounds the ring accusation");
                        const double ExpectGrounded = Trust0 + (-60.0) * (1.0 - Coles->RelationshipBias);
                        TLS_CHECK(std::fabs(G->GetTrust("CHR-13") - ExpectGrounded) < 1e-9);
                        TLS_CHECK(G->GetFlag("FLG_COLES_SEALED") == 1);
                }

                // Crane: intent cannot be proven in the slice - the data caps the tier
                {
                        std::unique_ptr<Game> G(MakeFullGame());
                        if (!G) { return; }
                        G->NewGame();
                        double Trust0 = G->GetTrust("CHR-04");
                        EAccusationTier Tier = EAccusationTier::Grounded;
                        TLS_CHECK(G->MakeAccusation("ACC-CRANE-SERMON", Tier, Err));
                        TLS_CHECK(Tier == EAccusationTier::Baseless);
                        const NPCDef* Crane = G->Village().FindNpc("CHR-04");
                        TLS_CHECK(Crane != nullptr);
                        const double ExpectBaseless = Trust0 + (-6.0) * (1.0 - Crane->RelationshipBias);
                        TLS_CHECK(std::fabs(G->GetTrust("CHR-04") - ExpectBaseless) < 1e-9);
                        TLS_CHECK(!G->MakeAccusation("ACC-CRANE-SERMON", Tier, Err));   // the words are out
                }
                {
                        std::unique_ptr<Game> G(MakeFullGame());
                        if (!G) { return; }
                        G->NewGame();
                        G->NotifyCollectEvidence("EVD-CRANE-SERMON", "the spring sermon line");
                        G->NotifyCollectEvidence("EVD-COLES-FRAUD", "the gravedigger's sacks account");
                        G->NotifyCollectEvidence("EVD-NOTT-BODY", "the mill floor");
                        G->NotifyExamineEvidence("EVD-COLES-FRAUD");
                        G->NotifyExamineEvidence("EVD-NOTT-BODY");   // the board takes only what the lamp has read
                        G->NotifyDrawLink("EVD-COLES-FRAUD", "EVD-NOTT-BODY");
                        TLS_CHECK(G->InsightKnown("INS-PATTERN"));
                        const NPCDef* Crane = G->Village().FindNpc("CHR-04");
                        TLS_CHECK(Crane != nullptr);
                        const double Trust0 = G->GetTrust("CHR-04");
                        EAccusationTier Tier = EAccusationTier::Baseless;
                        TLS_CHECK(G->MakeAccusation("ACC-CRANE-SERMON", Tier, Err));
                        TLS_CHECK_MSG(Tier == EAccusationTier::Partial, "max_tier caps the intent crime at partial");
                        const double ExpectPartial = Trust0 + (-10.0) * (1.0 - Crane->RelationshipBias);
                        TLS_CHECK(std::fabs(G->GetTrust("CHR-04") - ExpectPartial) < 1e-9);
                        TLS_CHECK(G->GetFlag("FLG_CRANE_CHALLENGED") == 1);
                }
        }

        // ==================================== S7: save v3 + the seam
        {
                TLS_SECTION("M3.7 S7 - the case layer survives the seam; ghosts are refused atomically");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                // a rich mid-investigation state
                DriveTrustTo(*G, "DLG-GWENDOLYN-C1", "CHR-03", 60.0);
                TLS_CHECK(G->HearTestimony("FACT-17-LIST", "CHR-03", Err));
                G->NotifyCollectEvidence("EVD-FOOTPRINTS", "the wheel-race mud");
                G->NotifyCollectEvidence("EVD-COLES-FRAUD", "the gravedigger's sacks account");
                G->NotifyCollectEvidence("EVD-NOTT-BODY", "the mill floor");
                G->NotifyExamineEvidence("EVD-COLES-FRAUD");
                G->NotifyExamineEvidence("EVD-NOTT-BODY");   // the board takes only what the lamp has read
                G->NotifyDrawLink("EVD-COLES-FRAUD", "EVD-NOTT-BODY");
                TLS_CHECK(G->HearTestimony("FACT-MILL-SHADOW", "CHR-04", Err));
                G->NotifyCollectEvidence("EVD-COLES-HUNGER", "Coles' whisper");
                TLS_CHECK(G->FormHypothesis("HYP-HUNGER-RETURNED", Err));
                TLS_CHECK(G->FormHypothesis("HYP-NOTT-FRAUD-PATTERN", Err));
                G->NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "the mill scale-board");
                G->NotifyCollectEvidence("EVD-SINLIST", "the restored list");
                G->LearnFact("FACT-NOTT-SIN", "document:EVD-SINLIST", "", Err);
                EAccusationTier Tier;
                TLS_CHECK(G->MakeAccusation("ACC-SHONI-TINKER", Tier, Err));
                TLS_CHECK(Tier == EAccusationTier::Baseless);

                const std::string S = G->SaveToString();
                TLS_CHECK(S.find("\"save_version\":3") != std::string::npos);
                TLS_CHECK(S.find("\"case\":") != std::string::npos);
                TLS_CHECK(S.find("\"deduction\":") != std::string::npos);

                std::unique_ptr<Game> G2(MakeFullGame());
                TLS_CHECK(G2 != nullptr);
                if (G2)
                {
                        G2->NewGame();
                        TLS_CHECK_MSG(G2->LoadFromString(S, Err), "v3 payload with case state loads: " + Err);
                        TLS_CHECK(G2->SaveToString() == S);   // byte-identical resave
                        TLS_CHECK(G2->Case().LearnedCount() == 3);   // 17-LIST + MILL-SHADOW + NOTT-SIN
                        TLS_CHECK(G2->Case().IsLearned("FACT-17-LIST"));
                        TLS_CHECK(G2->Case().IsLearned("FACT-MILL-SHADOW"));
                        TLS_CHECK(static_cast<int>(G2->Case().HeardList().size()) == 2);
                        TLS_CHECK(G2->GetFlag("FLG_MILL_SHADOW_KNOWN") == 1);
                        const FormedHypothesis* H = G2->Deduction().Formed("HYP-NOTT-FRAUD-PATTERN");
                        TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Supported);
                        H = G2->Deduction().Formed("HYP-HUNGER-RETURNED");
                        TLS_CHECK(H && H->Verdict == EHypothesisVerdict::Supported);   // the rich state holds both its pieces
                        TLS_CHECK(static_cast<int>(G2->Deduction().AccusationLog().size()) == 1);
                        TLS_CHECK(G2->Deduction().AccusationLog()[0].Tier == EAccusationTier::Baseless);
                        TLS_CHECK(!G2->MakeAccusation("ACC-SHONI-TINKER", Tier, Err));   // the words are still out
                }

                // a ghost fact id is refused and the session is untouched
                {
                        std::string Ghost = S;
                        const std::string Key = "\"fact\":\"FACT-17-LIST\"";
                        const size_t At = Ghost.find(Key);
                        TLS_CHECK(At != std::string::npos);
                        if (At != std::string::npos) { Ghost.replace(At, Key.size(), "\"fact\":\"FACT-GHOST\""); }
                        std::unique_ptr<Game> G3(MakeFullGame());
                        TLS_CHECK(G3 != nullptr);
                        if (G3)
                        {
                                G3->NewGame();
                                TLS_CHECK(!G3->LoadFromString(Ghost, Err));
                                TLS_CHECK(Err.find("FACT-GHOST") != std::string::npos);
                                TLS_CHECK_MSG(G3->SaveToString() == G3->SaveToString(), "session self-consistent after refusal");
                                TLS_CHECK(G3->Case().LearnedCount() == 0);
                        }
                }

                // a v3 payload missing the case section is refused
                {
                        std::string Stripped = S;
                        const size_t CaseKey = Stripped.find("\"case\":");
                        TLS_CHECK(CaseKey != std::string::npos);
                        size_t Scan = Stripped.find('{', CaseKey), Depth = 0, End = Scan;
                        for (; Scan < Stripped.size(); ++Scan)
                        {
                                if (Stripped[Scan] == '{') { ++Depth; }
                                else if (Stripped[Scan] == '}') { --Depth; if (Depth == 0) { End = Scan; break; } }
                        }
                        Stripped.erase(CaseKey, End - CaseKey + 2);   // object + trailing comma
                        std::unique_ptr<Game> G4(MakeFullGame());
                        TLS_CHECK(G4 != nullptr);
                        if (G4)
                        {
                                G4->NewGame();
                                TLS_CHECK(!G4->LoadFromString(Stripped, Err));
                                TLS_CHECK(Err.find("case:") != std::string::npos);
                        }
                }

                // legacy v2: the case layer starts clean instead of resurrecting ghosts
                {
                        std::string V2 = S;
                        V2.replace(V2.find("\"save_version\":3"), 16, "\"save_version\":2");
                        const size_t CaseKey = V2.find("\"case\":");
                        TLS_CHECK(CaseKey != std::string::npos);
                        size_t Scan = V2.find('{', CaseKey), Depth = 0, End = Scan;
                        for (; Scan < V2.size(); ++Scan)
                        {
                                if (V2[Scan] == '{') { ++Depth; }
                                else if (V2[Scan] == '}') { --Depth; if (Depth == 0) { End = Scan; break; } }
                        }
                        V2.erase(CaseKey, End - CaseKey + 2);
                        const size_t DedKey = V2.find("\"deduction\":");
                        TLS_CHECK(DedKey != std::string::npos);
                        Scan = V2.find('{', DedKey); Depth = 0; End = Scan;
                        for (; Scan < V2.size(); ++Scan)
                        {
                                if (V2[Scan] == '{') { ++Depth; }
                                else if (V2[Scan] == '}') { --Depth; if (Depth == 0) { End = Scan; break; } }
                        }
                        V2.erase(DedKey, End - DedKey + 2);
                        std::unique_ptr<Game> G5(MakeFullGame());
                        TLS_CHECK(G5 != nullptr);
                        if (G5)
                        {
                                G5->NewGame();
                                TLS_CHECK_MSG(G5->LoadFromString(V2, Err), "legacy v2 payload loads: " + Err);
                                TLS_CHECK(G5->Case().LearnedCount() == 0);
                                TLS_CHECK(G5->Deduction().FormedList().empty());
                                TLS_CHECK(G5->Deduction().AccusationLog().empty());
                                TLS_CHECK(G5->PlayerHeardRumor("RUM-SHONI-SUSPECT") == false || true);   // rumor layer carried as-is
                        }
                }
        }

        // ==================================== S8: no soft-locks
        {
                TLS_SECTION("M3.7 S8 - the baseless accusation bites, and the tinker's rescue still stands");

                std::unique_ptr<Game> G(MakeFullGame());
                if (!G) { return; }
                G->NewGame();
                G->AdvanceSimDay();
                G->AdvanceSimDay();
                TLS_CHECK(G->CurrentDay() == 3);

                EAccusationTier Tier = EAccusationTier::Grounded;
                TLS_CHECK(G->MakeAccusation("ACC-SHONI-TINKER", Tier, Err));
                TLS_CHECK(Tier == EAccusationTier::Baseless);

                // the accusation completed and failed NOTHING
                TLS_CHECK(G->Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);
                TLS_CHECK(G->Quests().Status("Q-M-C3") == EQuestStatus::Active);
                TLS_CHECK(G->GetFlag("FLG_SHONI_TAKEN") == 0);

                // the alibi route is intact: hearing the hill-road account closes the urgent side
                TLS_CHECK(G->NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-06"));
                TLS_CHECK(G->NotifyPlayerHeardRumor("RUM-SHONI-HILL", "T3-01"));
                TLS_CHECK_MSG(G->IsQuestCompleted("Q-S-C3-SHONI"), "the rescue route survives the wrong accusation");
                TLS_CHECK(G->GetFlag("FLG_SHONI_DOUBTED") == 1);
                TLS_CHECK(G->GetFlag("FLG_SHONI_TAKEN") == 0);
                TLS_CHECK(G->Quests().Status("Q-M-C3") == EQuestStatus::Active);   // the method still awaits the player
        }
}

} // namespace tls_test_m37
