// THE LAST SIN: The Sin-Eater - M2.1
// TLSRumors: the village rumor & witness engine.
// Pure C++17, no engine includes - compiled standalone (g++) and inside UE.
//
// Semantics per docs/NPC_SIMULATION.md 4-6 (knowledge/belief, rumor engine,
// witnesses) and the M2 brief:
//   - every rumor: unique id, origin, timing, place, reliability, hop log
//   - four testimony kinds: Direct / Hearsay / Inference / Unverified
//   - spread tied to daily schedules (co-location in gossip zones), NPC-NPC
//     relationships and reticence - never an instant broadcast
//   - content mutates hop by hop, provenance always traceable
//   - no infinite re-gossip, no duplicate event recording
//   - NPCs act only on what they actually know (query API, not world truth)

#pragma once

#include "TLSCoreTypes.h"
#include "TLSJson.h"
#include "TLSRng.h"
#include "TLSVillageState.h"

#include <map>
#include <set>
#include <string>
#include <vector>

namespace tls
{

// ------------------------------------------------------------- enums

enum class ETestimonyKind
{
        Direct,       // witnessed the event themselves
        Hearsay,      // got it from another person
        Inference,    // their own conclusion (may be right or wrong)
        Unverified    // degraded hearsay: many hops / low confidence
};

const char* ToString(ETestimonyKind K);
bool ParseTestimonyKind(const std::string& S, ETestimonyKind& Out);

// ------------------------------------------------------------- data model

struct RumorSeed
{
        std::string NpcId;
        ETestimonyKind Kind = ETestimonyKind::Hearsay;
        double Confidence = 1.0;
        int VariantIndex = 0;
};

struct RumorDef
{
        std::string Id;
        std::string Topic;             // conflict key: two rumors on one topic can contradict
        std::string Subject;           // "EDMUND" / "SHONI" / "HUNGER" / ... ("EDMUND" rumors follow trust rules)
        double Valence = 0.0;          // -1 (maligning) .. +1 (favourable) - ground truth of the claim
        std::string Origin;            // npc id or "world:<event>"
        int DayCreated = 1;
        int HourCreated = 8;
        std::string PlaceZone;         // where it was born
        double OriginConfidence = 1.0; // how reliable the origin account is
        double Decay = 0.25;           // per-day confidence decay for holders
        double TensionOnSpread = 0.0;  // tension added on the first spread day
        std::vector<std::string> Variants;  // [0] = pure wording, later = distorted wordings
        std::vector<RumorSeed> Seeds;       // NPCs that know it when it is born
};

struct RumorKnowledge
{
        std::string RumorId;
        ETestimonyKind Kind = ETestimonyKind::Hearsay;
        int HopCount = 0;              // 0 = origin/witness, N = N transfers away
        double Confidence = 1.0;       // 0..1, decays with hops and days
        int Day = 1;                   // when acquired
        int Hour = 8;
        std::string FromNpc;           // "" for direct / seeded knowledge
        std::string WhereZone;         // where it was heard
        int VariantIndex = 0;          // which wording this holder carries
};

// One recorded transfer. Append-only; the dedupe key is (rumor, from, to, day, hour).
struct RumorTransmission
{
        std::string RumorId;
        std::string FromNpc;
        std::string ToNpc;
        int Day = 1;
        int Hour = 8;
        std::string Zone;
        int VariantIndex = 0;
};

// ------------------------------------------------------------- engine

class RumorSystem
{
public:
        // ---- loading ----
        // Root: { schema, gossip_zones[], rules{...}, npc_relationships{a:b:val}, rumors[] }
        bool Load(const JsonValue& Root, std::string& OutError);

        // ---- witness events ----
        // Registers an observable world event: every listed witness gains Direct
        // knowledge at that moment. Duplicate (event, witness) registrations are
        // ignored - no double bookkeeping.
        bool RegisterWitnessEvent(const std::string& RumorId, int Day, int Hour, const std::string& Zone,
                const std::vector<std::string>& WitnessNpcIds, std::string& OutError);

        // ---- simulation ----
        // Seeds every rumor def whose day_created == Day (idempotent - a rumor
        // whose day already ran, or whose holders all know it, stays untouched).
        // Game calls this on NewGame (day 1) and on every BeginDay.
        void ActivateDue(int Day);
        struct TickResult
        {
                std::vector<RumorTransmission> NewTransmissions;
                std::vector<std::string> RumorsThatFirstSpread;   // tension events, once per rumor
                int NewKnowersToday = 0;                          // counted against the daily cap
                bool bDailyCapReached = false;
        };
        // One hour of village gossip. Deterministic given (VillageState, Rng state).
        // VillageState provides schedules (who is where) and trust toward Edmund.
        TickResult TickHour(int Day, int Hour, const VillageState& Village, Rng& Rng);

        // Per-day decay. Call once per BeginDay. Holders below the forget threshold
        // lose the rumor entirely (spread naturally dies out).
        void ApplyDailyDecay(int Day);

        // ---- player tools (NPC_SIMULATION 5) ----
        // The player heard the rumor (journal/dialogue integration, quest tasks).
        bool NotifyPlayerHeard(const std::string& RumorId, int Day, int Hour, const std::string& FromNpc);
        // Public denial: every current holder loses confidence; spread that day is dulled.
        // Returns the number of holders affected.
        int NotifyPlayerDenial(int Day, int Hour);
        // The player's third rumor tool (NPC_SIMULATION 5): the anonymous leak.
        // Everyone currently in the gossip zone (per the village schedule at Hour)
        // hears the rumor as unverified anonymous word - hop 0, source "PLAYER".
        // Deterministic: no RNG, the schedule decides who listens.
        // Returns the number of NPCs that received it; OutError names the problem.
        int NotifyPlayerLeak(const std::string& RumorId, int Day, int Hour, const std::string& Zone,
                const VillageState& Village, std::string& OutError);

        // ---- queries (behavior consistency: act on what you KNOW) ----
        const RumorKnowledge* NpcKnowledge(const std::string& NpcId, const std::string& RumorId) const;
        bool NpcKnows(const std::string& NpcId, const std::string& RumorId) const;
        // Effective kind: stored kind, except degraded hearsay (low confidence or
        // heavy mutation) reports as Unverified.
        ETestimonyKind NpcEffectiveKind(const std::string& NpcId, const std::string& RumorId) const;
        std::vector<std::string> NpcsKnowing(const std::string& RumorId) const;
        int KnowerCount(const std::string& RumorId) const;
        std::vector<std::string> ActiveRumorIds() const;   // at least one holder
        // Rumors the player has heard (in order of first hearing).
        const std::vector<std::string>& PlayerKnownRumors() const { return PlayerKnown; }

        // Two rumors on the same topic with opposite valence that this NPC knows.
        struct RumorConflict
        {
                std::string RumorA;
                std::string RumorB;
                std::string Topic;
        };
        std::vector<RumorConflict> FindConflicts(const std::string& NpcId) const;

        // Provenance: the transfer chain from origin down to this holder.
        // Each step must be an actual recorded transmission.
        std::vector<RumorTransmission> TraceProvenance(const std::string& RumorId, const std::string& NpcId) const;
        const std::vector<RumorTransmission>& TransmissionLog() const { return Transmissions; }

        const std::map<std::string, RumorDef>& Defs() const { return RumorDefs; }
        const RumorDef* FindDef(const std::string& RumorId) const;

        // ---- save / load (M2.2 format v2) ----
        JsonValue SerializeState() const;
        bool DeserializeState(const JsonValue& Root, std::string& OutError);

        // tuning (loaded from data, defaults match NPC_SIMULATION caps)
        struct Rules
        {
                int MaxActiveRumors = 6;
                double DailySpreadCap = 0.30;      // fraction of population newly informed per day
                double BaseChance = 0.60;          // base transmission chance per (speaker, listener, hour)
                double MutationChance = 0.25;      // per hop
                double HopConfidence = 0.80;       // confidence multiplier per hop
                double DailyDecay = 0.25;          // confidence multiplier per day
                double ForgetBelow = 0.15;         // knowledge dropped under this confidence
                int SpeakerHourlyBudget = 1;       // max rumors told by one NPC per hour
                int SpeakerDailyBudget = 3;        // max rumors told by one NPC per day
                double ReticenceBlock = 0.75;      // effective reticence >= this: says nothing
        };
        const Rules& GetRules() const { return RulesCfg; }
        bool IsGossipZone(const std::string& Zone) const;
        double Relationship(const std::string& A, const std::string& B) const;

private:
        void SeedRumor(const RumorDef& Def);
        bool AlreadyTransmitted(const std::string& RumorId, const std::string& From, const std::string& To,
                int Day, int Hour) const;

        std::map<std::string, RumorDef> RumorDefs;
        std::map<std::string, std::map<std::string, RumorKnowledge>> Knowledge;   // npc -> rumor -> state
        std::vector<RumorTransmission> Transmissions;
        std::map<std::string, std::set<std::string>> WitnessLog;                  // event rumor -> witnesses
        std::set<std::string> FirstSpreadDone;                                    // rumors that already fired tension
        std::map<int, int> NewKnowersPerDay;                                      // day -> new knowers (daily spread cap)
        int LastDenialDay = -1;                                                   // public denial dulls spread that day
        std::map<std::string, int> SpeakerDailyCount;                             // "day|npc" -> count
        std::vector<std::string> PlayerKnown;
        std::set<std::string> GossipZones;
        std::map<std::string, std::map<std::string, double>> Relationships;       // a -> b -> -100..100
        Rules RulesCfg;
};

} // namespace tls
