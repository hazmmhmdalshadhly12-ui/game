// THE LAST SIN: The Sin-Eater - M3.7
// TLSDeduction: hypotheses, open questions and formal accusations.
// Pure C++17, no engine includes - compiled standalone (g++) and inside UE.
//
// Semantics per docs/QUEST_ARCHITECTURE.md 2.1 (the E1 reliability bar:
// "a case file whose evidence is mostly reliability >= 0.7") and 6 (decisions
// and flags). Design contract (master brief, pillars B + D):
//   - a hypothesis is a PLAYER construction; the engine never suggests one;
//   - verdicts are deterministic functions of real game state
//     (insights/evidence/facts/board contradictions) - never hidden flags;
//   - missing hypothesis pieces surface as open questions (the board's
//     "unresolved questions" shelf) and shrink as evidence arrives;
//   - an accusation is always speakable; its TIER (baseless / partial /
//     grounded) is computed from the grounding bundle, and each tier carries
//     its own believable, data-declared consequences - a wrong accusation
//     must cost something real but must never soft-lock the mystery.

#pragma once

#include "TLSCoreTypes.h"
#include "TLSJson.h"

#include <map>
#include <set>
#include <string>
#include <vector>

namespace tls
{

class CaseFactSystem;   // facts feed hypothesis requirements

// ------------------------------------------------------------ hypotheses

struct HypothesisDef
{
        std::string Id;                        // HYP-...
        std::string Title;
        std::string SuspectLabel;              // display label; "" for non-suspect hypotheses
        std::string SuspectNpc;                // sim npc id when the suspect is a village NPC ("" allowed)
        std::string MethodSummary;
        std::string MotiveSummary;
        std::vector<std::string> RequiresInsights;   // all required for SUPPORTED
        std::vector<std::string> RequiresEvidence;   // all required (collected)
        std::vector<std::string> RequiresFacts;      // all required (learned)
        struct Refuter
        {
                enum class Kind { Flag, Fact, Contradiction, PlayerRumor };
                Kind KindV = Kind::Flag;
                std::string Target;            // flag id / fact id / link-rule id / rumor id
                std::string Reason;            // shown when the hypothesis collapses
        };
        std::vector<Refuter> RefutedBy;
        std::string CanonRef;                  // REQUIRED - no hypothesis without a canon anchor
};

// ------------------------------------------------------------ accusations

enum class EAccusationTier
{
        Baseless,   // no grounding at all - the player spoke without a case
        Partial,    // some grounding, the bundle is incomplete (or capped by data)
        Grounded    // the full grounding bundle stands behind the accusation
};

const char* ToString(EAccusationTier T);
bool ParseAccusationTier(const std::string& S, EAccusationTier& Out);

struct AccusationConsequences
{
        double TrustDeltaTarget = 0.0;    // applied to the target npc (skipped when not a sim npc)
        double TensionDelta = 0.0;
        double ReputationDelta = 0.0;
        std::map<std::string, int> SetFlags;
        std::string JournalNote;
};

struct AccusationDef
{
        std::string Id;                        // ACC-...
        std::string TargetLabel;               // display name ("Shoni Gwyn", "the dead man's memory")
        std::string TargetNpc;                 // sim npc id for trust consequences ("" allowed)
        std::string Topic;                     // what is being alleged
        bool bAlwaysBaseless = false;          // data-declared: no bundle can ever ground this accusation
        std::string GroundingInsight;          // the insight that anchors the case ("" allowed)
        std::vector<std::string> GroundingEvidence;   // all required (collected)
        std::string GroundingFact;             // case fact that must be learned ("" allowed)
        double MinReliability = 0.0;           // average reliability bar over GroundingEvidence (QUEST 2.1)
        EAccusationTier MaxTier = EAccusationTier::Grounded;   // data can cap (intent crimes stay partial)
        bool bRepeatable = false;              // false: speaking the words twice is refused
        AccusationConsequences OnGrounded;
        AccusationConsequences OnPartial;
        AccusationConsequences OnBaseless;
        std::string CanonRef;                  // REQUIRED
};

// ------------------------------------------------------------ state

enum class EHypothesisVerdict { Unsupported, Partial, Supported, Refuted };
const char* ToString(EHypothesisVerdict V);

struct FormedHypothesis
{
        std::string HypId;
        int DayFormed = 1;
        int LastEvalDay = 1;
        EHypothesisVerdict Verdict = EHypothesisVerdict::Unsupported;
        std::string RefuteReason;              // set when Refuted
};

struct OpenQuestion
{
        std::string HypId;
        std::string Kind;                      // "insight" | "evidence" | "fact"
        std::string TargetId;
        std::string Question;
};

struct AccusationRecord
{
        std::string AccId;
        EAccusationTier Tier = EAccusationTier::Baseless;
        int Day = 1;
        int Hour = 8;
};

// ------------------------------------------------------------ engine

class DeductionSystem
{
public:
        // Root: { schema, slice, hypotheses[], accusations[] }. Strict.
        bool Load(const JsonValue& Root, std::string& OutError);

        const HypothesisDef* FindHypothesis(const std::string& Id) const;
        const std::map<std::string, HypothesisDef>& Hypotheses() const { return HypDefs; }
        const AccusationDef* FindAccusation(const std::string& Id) const;
        const std::map<std::string, AccusationDef>& Accusations() const { return AccDefs; }

        // ---- hypotheses ----
        bool FormHypothesis(const std::string& HypId, int Day, std::string& OutError);
        bool IsFormed(const std::string& HypId) const;
        const FormedHypothesis* Formed(const std::string& HypId) const;
        std::vector<FormedHypothesis> FormedList() const;
        // Re-evaluates every formed hypothesis against current state.
        // Deterministic: same state, same verdicts.
        void RecheckAll(const IGameContext& Ctx, const CaseFactSystem& Facts, int Day);
        // Missing pieces of formed hypotheses - the open-questions shelf.
        std::vector<OpenQuestion> OpenQuestions(const IGameContext& Ctx, const CaseFactSystem& Facts) const;

        // ---- accusations ----
        // M3.8: the accusation UI's strength readout - the tier the
        // accusation WOULD land at right now, from live state, WITHOUT
        // recording it or applying consequences. Same evaluation
        // MakeAccusation uses, so the preview never lies.
        EAccusationTier PreviewTier(const std::string& AccId, const IGameContext& Ctx,
                const CaseFactSystem& Facts) const;
        // Evaluates the tier from current state, records it, and returns the
        // tier so the caller (Game) applies the matching consequences.
        bool MakeAccusation(const std::string& AccId, const IGameContext& Ctx, const CaseFactSystem& Facts,
                int Day, int Hour, EAccusationTier& OutTier, std::string& OutError);
        bool AccusedBefore(const std::string& AccId) const;
        std::vector<AccusationRecord> AccusationLog() const { return AccLog; }

        // ---- save / load (strict) ----
        JsonValue SerializeState() const;
        bool DeserializeState(const JsonValue& Root, std::string& OutError);

private:
        EHypothesisVerdict Evaluate(const HypothesisDef& Hyp, const IGameContext& Ctx,
                const CaseFactSystem& Facts, std::string& OutRefuteReason) const;
        // The deterministic tier function shared by PreviewTier and
        // MakeAccusation (one evaluation, two consumers - they cannot drift).
        EAccusationTier EvaluateTier(const AccusationDef& Def, const IGameContext& Ctx,
                const CaseFactSystem& Facts) const;

        std::map<std::string, HypothesisDef> HypDefs;
        std::map<std::string, AccusationDef> AccDefs;
        std::map<std::string, FormedHypothesis> FormedMap;   // hyp -> state
        std::vector<AccusationRecord> AccLog;
        std::set<std::string> AccUsed;
};

} // namespace tls
