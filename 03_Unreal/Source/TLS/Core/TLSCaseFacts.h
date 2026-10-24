// THE LAST SIN: The Sin-Eater - M3.7
// TLSCaseFacts: the case-fact ledger - the canonical facts of the mystery,
// per-NPC testimony variants (what each character actually knows, believes,
// conceals or lies about), NPC dossiers (motive / fear / secrets) and the
// player's learned-fact tracking.
// Pure C++17, no engine includes - compiled standalone (g++) and inside UE.
//
// Semantics per docs/CHARACTER_REGISTRY.md (the Knowledge Ledger table and
// the T1/T2 secret/motive canon), docs/NPC_SIMULATION.md 4 (knowledge vs
// belief) and docs/QUEST_ARCHITECTURE.md 2 (testimonial evidence follows the
// witness). Design contract (master brief, pillars A + C):
//   - an NPC speaks ONLY their own variant of a fact, gated by reveal
//     conditions evaluated against real game state (never world truth);
//   - testimonies may agree, conflict, omit, or be deliberate misdirection -
//     every deliberate lie carries a data-declared narrative reason;
//   - the underlying truth of each fact is fixed in data (canon_ref) and is
//     never produced by simulation or AI;
//   - learning a fact can set flags, so discoveries in one part of the
//     village open dialogue elsewhere through the EXISTING condition types.

#pragma once

#include "TLSCoreTypes.h"
#include "TLSJson.h"

#include <map>
#include <set>
#include <string>
#include <vector>

namespace tls
{

// ------------------------------------------------------------ testimony

// What stance does this NPC take on the fact?
enum class ETestimonyStance
{
        Affirms,   // states the fact as they know it (matches the truth for honest witnesses)
        Denies,    // denies the fact happened (mistaken or covering)
        Claims,    // asserts a DIFFERENT claim instead (see ClaimText)
        Omits      // refuses to speak about it / claims not to know
};

const char* ToString(ETestimonyStance S);
bool ParseTestimonyStance(const std::string& S, ETestimonyStance& Out);

// How did this NPC come to know (or believe) their variant?
// Mirrors the rumor-testimony kinds (NPC_SIMULATION 4).
enum class ETestimonyOrigin
{
        Witnessed,   // saw/heard it themselves
        Told,        // someone told them (OriginSource names whom)
        Inferred,    // their own conclusion - may be wrong
        Documented   // read it in a document they had access to
};

const char* ToString(ETestimonyOrigin O);
bool ParseTestimonyOrigin(const std::string& S, ETestimonyOrigin& Out);

// When will this NPC share their variant? Evaluated against IGameContext
// (real game state) - the same condition style as dialogue conditions.
struct RevealConditions
{
        double TrustMin = -100.0;
        std::vector<std::string> RequiresEvidence;   // collected
        std::vector<std::string> RequiresInsights;   // known
        std::map<std::string, int> RequiresFlags;    // flag == value
        int DayMin = 1;
};

struct TestimonyDef
{
        std::string NpcId;
        ETestimonyStance Stance = ETestimonyStance::Affirms;
        std::string Account;          // what they say, in their voice
        std::string ClaimText;        // for Claims: the different claim they assert
        ETestimonyOrigin Origin = ETestimonyOrigin::Witnessed;
        std::string OriginSource;     // for Told: whom; for Documented: which document
        double Reliability = 0.5;     // judicial weight of this account (0..1)
        bool bDeliberate = false;     // true = they KNOW their account is false
        std::string LieReason;        // required when bDeliberate (narrative explanation)
        bool bGrantsFact = true;      // hearing this account counts as learning the fact
                                      // (false: an honest-but-wrong account, or a silence -
                                      //  the board may show it without teaching the truth)
        RevealConditions Reveal;
};

// ------------------------------------------------------------ facts

struct CaseFactDef
{
        std::string Id;               // FACT-...
        std::string Topic;            // grouping key (e.g. "nott-death")
        std::string TruthSummary;     // the canonical truth (validator/test-facing; never shown to the player)
        std::string CanonRef;         // canon anchor: "CHARACTER_REGISTRY.md CHR-xx" etc. - REQUIRED
        bool bTruthAnchor = false;    // true = no NPC reveals this in the current slice (the truth stays consistent)
        std::vector<std::string> RelatedEvidence;
        std::vector<TestimonyDef> Testimonies;
        std::map<std::string, int> OnLearnedFlags;
        std::string JournalNote;      // journal line when first learned
};

// ------------------------------------------------------------ dossiers

// Machine-readable T1/T2 dossier (pillars A + C). Every field is canon -
// the validator refuses a dossier whose secret facts the NPC has no
// testimony for (concealment must be playable, not decorative).
struct DossierDef
{
        std::string NpcId;
        std::string PublicMotive;     // what they present
        std::string DeepMotive;       // what actually drives them
        std::string Fear;             // what they are afraid of losing
        std::vector<std::string> SecretFacts;   // fact ids they conceal (must have a testimony with reveal gates)
        std::vector<std::string> RelationshipNotes;  // canon relationship lines
};

// ------------------------------------------------------------ state

struct LearnedFact
{
        std::string FactId;
        int Day = 1;
        int Hour = 8;
        std::string Via;              // "testimony" | "document" | "witness" | ...
        std::string FromNpc;          // "" when not from a person
};

// One heard testimony (the player heard THIS NPC's account of THIS fact).
struct HeardTestimony
{
        std::string FactId;
        std::string NpcId;
        int Day = 1;
        int Hour = 8;
};

// ------------------------------------------------------------ engine

class CaseFactSystem
{
public:
        // Root: { schema, slice, facts[], dossiers[] }. Strict: unknown
        // stances/origins, missing canon_ref, deliberate lies without a reason,
        // duplicate ids and unknown npc-id formats are refused.
        bool Load(const JsonValue& Root, std::string& OutError);

        // ---- queries (defs) ----
        const CaseFactDef* FindFact(const std::string& Id) const;
        const std::map<std::string, CaseFactDef>& Facts() const { return FactDefs; }
        const DossierDef* FindDossier(const std::string& NpcId) const;
        const std::map<std::string, DossierDef>& Dossiers() const { return DossierDefs; }
        const TestimonyDef* FindTestimony(const std::string& FactId, const std::string& NpcId) const;

        // The NPC's account RIGHT NOW - null when the reveal conditions do not
        // pass. This is the knowledge boundary: an NPC never produces an
        // account their conditions do not allow, whatever the caller asks.
        const TestimonyDef* GetAvailableTestimony(const std::string& FactId, const std::string& NpcId,
                const IGameContext& Ctx) const;

        // ---- conflicts (deterministic derivation from stances) ----
        struct FactConflict
        {
                std::string FactId;
                std::string NpcA;
                std::string NpcB;
                std::string Reason;   // data-declared when a lie, derived otherwise
        };
        // Two testimonies on one fact conflict when their stances disagree
        // (affirms vs denies/claims) or both claim different texts. Omits never
        // conflicts (silence is not an assertion). Only AVAILABLE testimonies
        // (reveal conditions passing) are compared - the board never shows a
        // contradiction the player could not have heard.
        std::vector<FactConflict> FindConflicts(const std::string& FactId, const IGameContext& Ctx) const;

        // ---- state transitions ----
        // The player heard this NPC's account (call AFTER GetAvailableTestimony
        // passed). Learns the fact (first hearing wins), applies OnLearnedFlags
        // into OutFlagsToSet for the caller (Game) to apply.
        bool NotifyTestimonyHeard(const std::string& FactId, const std::string& NpcId, int Day, int Hour,
                std::map<std::string, int>& OutFlagsToSet, std::string& OutError);
        // Direct learning (a document, an observed event). Same flag/journal
        // contract as testimony hearing.
        bool NotifyFactLearned(const std::string& FactId, const std::string& Via, const std::string& FromNpc,
                int Day, int Hour, std::map<std::string, int>& OutFlagsToSet, std::string& OutError);

        // ---- queries (state) ----
        bool IsLearned(const std::string& FactId) const;
        const LearnedFact* LearnRecord(const std::string& FactId) const;
        bool TestimonyHeard(const std::string& FactId, const std::string& NpcId) const;
        std::vector<std::string> LearnedFactIds() const;
        std::vector<HeardTestimony> HeardList() const { return HeardLog; }
        size_t LearnedCount() const { return Learned.size(); }

        // ---- save / load (strict) ----
        JsonValue SerializeState() const;
        // Refuses unknown fact/npc ids - a hand-edited or foreign payload cannot
        // fabricate knowledge of facts that do not exist (M3.2 load contract).
        bool DeserializeState(const JsonValue& Root, std::string& OutError);

private:
        bool EvaluateReveal(const RevealConditions& R, const std::string& NpcId, const IGameContext& Ctx) const;
        void ApplyLearned(const std::string& FactId, const std::string& Via, const std::string& FromNpc,
                int Day, int Hour, std::map<std::string, int>& OutFlagsToSet, std::string& OutError);

        std::map<std::string, CaseFactDef> FactDefs;
        std::map<std::string, DossierDef> DossierDefs;
        std::map<std::string, LearnedFact> Learned;         // fact -> first learning
        std::vector<HeardTestimony> HeardLog;               // append-only
        std::set<std::string> HeardKey;                     // dedupe key fact|npc
};

} // namespace tls
