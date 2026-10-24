// THE LAST SIN: The Sin-Eater - M1
// TLSCoreTypes: the shared data model of the game-logic core.
// Pure C++17, no engine includes - compiled standalone (g++) and inside UE.
// Sources of truth for the semantics:
//   docs/QUEST_ARCHITECTURE.md  (evidence, quests, dialogue, flags, save)
//   docs/NPC_SIMULATION.md      (trust / reputation / tension / schedules)
//   docs/GAME_BIBLE.md 6.1/6.2  (core loop, tones, Welsh layer)

#pragma once

#include <map>
#include <string>
#include <vector>

namespace tls
{

// ------------------------------------------------------------------ enums

enum class EEvidenceType
{
        Physical,      // found in the world, examined on the table
        Testimonial,   // sworn/free statements - value follows the witness
        Documentary,   // ledger pages, papers, registers
        Hearsay        // mutated rumor - exploratory value only
};

enum class ETone
{
        Gentle,        // rqiqa
        Formal,        // rasmi
        Pressing,      // daghith
        Silent         // samt (listen, do not push)
};

enum class ETaskType
{
        Reach,         // player entered an area
        Observe,       // player saw a world evidence point
        Collect,       // player took the evidence
        Inspect,       // evidence examined on the father's table
        Restore,       // page restored with the etching skill
        Dialogue,      // a dialogue flag/node was reached
        Flag,          // a named flag reached a value
        Insight,       // an insight was unlocked on the ledger board
        NpcRumor,      // M2.3: a named NPC actually knows a rumor ("NPC=RUMOR")
        PlayerRumor,   // M2.3: the player has heard a rumor (rumor id)
        TensionBelow   // M2.3: village tension is below "value" (emergent state)
};

enum class EQuestStatus
{
        NotStarted,
        Active,
        Completed,
        Failed
};

enum class ETimeOfDay
{
        Morning,
        Noon,
        Afternoon,
        Evening,
        Night
};

enum class EWeather
{
        OvercastFog,   // Day 1 - the fog holds the swamp shut (WORLD_REGISTRY 4)
        Rain           // Day 2 - mud opens footprint paths
};

enum class EReaction   // evidence presentation reactions (QUEST_ARCHITECTURE 5)
{
        Accept,        // takes the card, answers straight
        Deny,          // denies -> recorded contradiction on their testimony
        Break          // a confession line slips out
};

// ------------------------------------------------------------- evidence

struct EvidenceDef
{
        std::string Id;
        std::string Name;
        std::string Description;      // short journal text
        std::string ExamineDetail;    // revealed only on the examination table
        EEvidenceType Type = EEvidenceType::Physical;
        double Reliability = 0.5;     // 0..1 - E1 judicial weight (QUEST 2.1)
        int DayAcquired = 1;          // narrative day the item becomes available
        std::string Source;           // where/whom it comes from
        bool bRestorable = false;     // torn pages repaired with the etching skill
};

struct LinkRule
{
        std::string Id;
        std::string A;
        std::string B;
        bool bValid = true;
        std::string InsightId;            // empty for supporting links
        std::string Note;                 // shown when drawn
        std::string ContradictionReason;  // shown when bValid == false
};

struct InsightDef
{
        std::string Id;
        std::string Name;
        std::string Description;
        std::vector<std::vector<std::string>> LinkPaths;  // OR of AND-sets of link ids
        std::vector<std::string> RequiresExamined;        // evidence that must be examined
};

// ------------------------------------------------------------- dialogue

struct DialogueConditions
{
        std::map<std::string, int> Flags;        // flag == value required
        int TrustMin = -100;
        int TrustMax = 100;
        std::vector<std::string> HasEvidence;    // all required in inventory
        std::vector<std::string> KnowsInsight;   // all required insights
        int WelshLevelMin = 0;
        int DayMin = 1;
        int DayMax = 9;
        std::vector<std::string> QuestDone;      // all quests completed
};

struct DialogueEffects
{
        double TrustDelta = 0.0;                 // raw; engine applies tone + bias + spillover
        std::map<std::string, int> SetFlags;
        std::vector<std::string> GiveEvidence;
        std::vector<std::string> GiveInsight;
        double ReputationDelta = 0.0;
        double TensionDelta = 0.0;
        bool bAdvanceToEvening = false;
};

struct DialogueChoice
{
        std::string Id;
        std::string Text;                        // may contain [wN:word] Welsh markers
        ETone Tone = ETone::Formal;
        std::string PresentEvidence;             // evidence id offered in-dialogue
        EReaction Reaction = EReaction::Accept;  // NPC reaction to the presented card
        DialogueConditions Conditions;
        DialogueEffects Effects;
        std::string Next;                        // empty -> dialogue ends after this
        bool bOptionalHint = false;              // rendered dimmed as a side thread
};

struct DialogueNode
{
        std::string Id;
        std::string Speaker;
        std::string Text;
        DialogueEffects OnEnter;
        std::vector<DialogueChoice> Choices;
        std::string Next;                        // node-level auto-continue (no choices)
};

struct DialogueDef
{
        std::string Id;
        std::string NpcId;
        std::string Root;
        std::map<std::string, DialogueNode> Nodes;
};

// ------------------------------------------------------------- quests

struct TaskDef
{
        ETaskType Type = ETaskType::Reach;
        std::string Target;                      // area id / evidence id / flag / insight / "DLG:node"
        int RequiredCount = 1;                   // for Flag: value required
};

struct ObjectiveDef
{
        std::string Id;
        std::string Description;
        std::vector<TaskDef> Tasks;
        bool bOptional = false;
        bool bAnyOf = false;                     // M2.3: any single task passing completes the objective (branch)
};

struct QuestDef
{
        std::string Id;
        std::string Title;
        std::string Chapter;                     // C1 / C2 ...
        int DayWindowMin = 1;
        int DayWindowMax = 9;
        bool bAutoStart = true;                  // activates when inside day window
        std::vector<ObjectiveDef> Objectives;
        std::map<std::string, int> FlagsOnComplete;
        bool bFailsOnExpiry = false;             // M2.3: still Active when the window closes -> Failed
        std::map<std::string, int> FlagsOnFail;  // M2.3: story consequence flags applied on failure
};

// ------------------------------------------------------------- village sim

struct ScheduleSegment
{
        int FromHour = 0;
        int ToHour = 24;
        std::string Zone;                        // area id
        std::string Activity;
        std::string Bark;                        // ambient line (may be empty)
};

struct NPCDef
{
        std::string Id;
        std::string Name;
        int Tier = 3;                            // 1 story / 2 secondary / 3 background
        std::string Faction;                     // inn / church / chapel / estate / mine / moor / none
        double InitialTrust = 0.0;               // -100..100 toward Edmund
        double RelationshipBias = 0.0;           // 0..1 - protects strong relations (NPC_SIM 3)
        double Reticence = 0.0;                  // 0..1 - how much this NPC holds their tongue (M2.1)
        std::map<ETone, double> ToneWeights;     // tone -> trust bonus/penalty
        std::vector<ScheduleSegment> Schedule;
        std::vector<ScheduleSegment> ScheduleTension;  // used when tension >= 3
        std::string VisualFamily;                // blockout visual family (T3 twins)
};

// ------------------------------------------------------------ helpers

// Read-only world view shared by quest evaluation and dialogue conditions.
// Implemented by tls::Game (TLSGameState.h).
class IGameContext
{
public:
        virtual ~IGameContext() = default;

        virtual int CurrentDay() const = 0;
        virtual ETimeOfDay GetTimeOfDay() const = 0;
        virtual EWeather GetWeather() const = 0;
        virtual bool HasReachedArea(const std::string& AreaId) const = 0;
        virtual bool EvidenceObserved(const std::string& Id) const = 0;
        virtual bool EvidenceCollected(const std::string& Id) const = 0;
        virtual bool EvidenceExamined(const std::string& Id) const = 0;
        virtual bool EvidenceRestored(const std::string& Id) const = 0;
        virtual bool InsightKnown(const std::string& Id) const = 0;
        virtual bool DialogueNodeSeen(const std::string& DialogueId, const std::string& NodeId) const = 0;
        virtual int GetFlag(const std::string& FlagId) const = 0;
        virtual bool IsQuestCompleted(const std::string& QuestId) const = 0;
        virtual double GetTrust(const std::string& NpcId) const = 0;
        virtual int GetWelshLevel() const = 0;
        // M2.1: rumor-aware conditions. Implemented by tls::Game; default no.
        virtual bool NpcKnowsRumor(const std::string& NpcId, const std::string& RumorId) const { (void)NpcId; (void)RumorId; return false; }
        virtual bool PlayerHeardRumor(const std::string& RumorId) const { (void)RumorId; return false; }
        // M2.3: village tension for emergent quest conditions (0..5).
        virtual double GetTension() const { return 0.0; }
        // M3.7: deduction-board queries for the hypothesis/accusation engine.
        // Additive with safe defaults so existing implementations keep working.
        // Was a named CONTRADICTION link rule ever drawn on the board?
        virtual bool ContradictionRuleDrawn(const std::string& RuleId) const { (void)RuleId; return false; }
        // Judicial weight of a collected piece of evidence (0..1); false when
        // the id is unknown or not collected.
        virtual bool EvidenceReliability(const std::string& Id, double& OutReliability) const
        {
                (void)Id; (void)OutReliability; return false;
        }
};

const char* ToString(EEvidenceType T);
const char* ToString(ETone T);
const char* ToString(ETaskType T);
const char* ToString(EQuestStatus S);
const char* ToString(ETimeOfDay T);
const char* ToString(EWeather W);
const char* ToString(EReaction R);

bool ParseEvidenceType(const std::string& S, EEvidenceType& Out);
bool ParseTone(const std::string& S, ETone& Out);
bool ParseTaskType(const std::string& S, ETaskType& Out);
bool ParseTimeOfDay(const std::string& S, ETimeOfDay& Out);
bool ParseWeather(const std::string& S, EWeather& Out);
bool ParseReaction(const std::string& S, EReaction& Out);

// Welsh layer: rewrites [wN:...] markers. When playerWelshLevel >= N the word
// shows as-is; otherwise each letter becomes '#' (muted word) and
// OutNeedsLesson is set. (GAME_BIBLE 6.2.5)
std::string RenderDialogueText(const std::string& Text, int PlayerWelshLevel, bool& OutNeedsLesson);

} // namespace tls
