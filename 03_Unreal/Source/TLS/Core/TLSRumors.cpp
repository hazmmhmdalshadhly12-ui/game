// THE LAST SIN: The Sin-Eater - M2.1
// TLSRumors.cpp

#include "TLSRumors.h"

#include <algorithm>
#include <cmath>

namespace tls
{

const char* ToString(ETestimonyKind K)
{
        switch (K)
        {
        case ETestimonyKind::Direct: return "direct";
        case ETestimonyKind::Hearsay: return "hearsay";
        case ETestimonyKind::Inference: return "inference";
        case ETestimonyKind::Unverified: return "unverified";
        }
        return "hearsay";
}

bool ParseTestimonyKind(const std::string& S, ETestimonyKind& Out)
{
        if (S == "direct") { Out = ETestimonyKind::Direct; return true; }
        if (S == "hearsay") { Out = ETestimonyKind::Hearsay; return true; }
        if (S == "inference") { Out = ETestimonyKind::Inference; return true; }
        if (S == "unverified") { Out = ETestimonyKind::Unverified; return true; }
        return false;
}

// ------------------------------------------------------------ loading

bool RumorSystem::Load(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "rumors root must be an object"; return false; }

        const JsonValue* Zones = Root.Find("gossip_zones");
        if (Zones && Zones->IsArray())
        {
                for (size_t I = 0; I < Zones->Size(); ++I)
                {
                        if (const JsonValue* Z = Zones->At(I)) { if (Z->IsString()) { GossipZones.insert(Z->AsString()); } }
                }
        }
        if (GossipZones.empty()) { OutError = "rumor data defines no gossip zones"; return false; }

        if (const JsonValue* R = Root.Find("rules"))
        {
                if (!R->IsObject()) { OutError = "rules must be an object"; return false; }
                RulesCfg.MaxActiveRumors = R->GetInt("max_active", RulesCfg.MaxActiveRumors);
                RulesCfg.DailySpreadCap = R->GetNumber("daily_spread_cap", RulesCfg.DailySpreadCap);
                RulesCfg.BaseChance = R->GetNumber("base_chance", RulesCfg.BaseChance);
                RulesCfg.MutationChance = R->GetNumber("mutation_chance", RulesCfg.MutationChance);
                RulesCfg.HopConfidence = R->GetNumber("hop_confidence", RulesCfg.HopConfidence);
                RulesCfg.DailyDecay = R->GetNumber("daily_decay", RulesCfg.DailyDecay);
                RulesCfg.ForgetBelow = R->GetNumber("forget_below", RulesCfg.ForgetBelow);
                RulesCfg.SpeakerHourlyBudget = R->GetInt("speaker_hourly_budget", RulesCfg.SpeakerHourlyBudget);
                RulesCfg.SpeakerDailyBudget = R->GetInt("speaker_daily_budget", RulesCfg.SpeakerDailyBudget);
                RulesCfg.ReticenceBlock = R->GetNumber("reticence_block", RulesCfg.ReticenceBlock);
                if (RulesCfg.DailySpreadCap <= 0.0 || RulesCfg.DailySpreadCap > 1.0)
                {
                        OutError = "daily_spread_cap must be in (0, 1]"; return false;
                }
        }

        if (const JsonValue* Rel = Root.Find("npc_relationships"))
        {
                if (!Rel->IsObject()) { OutError = "npc_relationships must be an object"; return false; }
                for (const auto& KV : Rel->AsObject())
                {
                        if (!KV.second.IsObject()) { OutError = "npc_relationships entry must be an object"; return false; }
                        for (const auto& Inner : KV.second.AsObject())
                        {
                                const double V = Inner.second.AsNumber(0.0);
                                if (V < -100.0 || V > 100.0) { OutError = "relationship out of range"; return false; }
                                Relationships[KV.first][Inner.first] = V;
                        }
                }
        }

        const JsonValue* Rumors = Root.Find("rumors");
        if (!Rumors || !Rumors->IsArray()) { OutError = "missing 'rumors' array"; return false; }
        for (size_t I = 0; I < Rumors->Size(); ++I)
        {
                const JsonValue* R = Rumors->At(I);
                if (!R || !R->IsObject()) { OutError = "rumor entry not an object"; return false; }
                RumorDef Def;
                Def.Id = R->GetString("id", "");
                if (Def.Id.empty()) { OutError = "rumor missing id"; return false; }
                if (RumorDefs.count(Def.Id)) { OutError = "duplicate rumor id " + Def.Id; return false; }
                Def.Topic = R->GetString("topic", Def.Id);
                Def.Subject = R->GetString("subject", "");
                Def.Valence = R->GetNumber("valence", 0.0);
                if (Def.Valence < -1.0 || Def.Valence > 1.0) { OutError = "valence out of range on " + Def.Id; return false; }
                Def.Origin = R->GetString("origin", "");
                if (Def.Origin.empty()) { OutError = "rumor " + Def.Id + " missing origin"; return false; }
                Def.DayCreated = R->GetInt("day_created", 1);
                Def.HourCreated = R->GetInt("hour_created", 8);
                Def.PlaceZone = R->GetString("place_zone", "");
                Def.OriginConfidence = R->GetNumber("origin_confidence", 1.0);
                Def.Decay = R->GetNumber("decay", 0.25);
                Def.TensionOnSpread = R->GetNumber("tension_on_spread", 0.0);
                Def.Variants = R->GetStringList("variants");
                if (Def.Variants.empty()) { OutError = "rumor " + Def.Id + " needs at least one variant"; return false; }

                if (const JsonValue* Seeds = R->Find("seeds"))
                {
                        for (size_t S = 0; S < Seeds->Size(); ++S)
                        {
                                const JsonValue* Sj = Seeds->At(S);
                                if (!Sj || !Sj->IsObject()) { OutError = "seed not an object on " + Def.Id; return false; }
                                RumorSeed Seed;
                                Seed.NpcId = Sj->GetString("npc", "");
                                if (Seed.NpcId.empty()) { OutError = "seed missing npc on " + Def.Id; return false; }
                                std::string KindStr = Sj->GetString("kind", "hearsay");
                                if (!ParseTestimonyKind(KindStr, Seed.Kind)) { OutError = "bad seed kind on " + Def.Id; return false; }
                                Seed.Confidence = Sj->GetNumber("confidence", 1.0);
                                Seed.VariantIndex = Sj->GetInt("variant", 0);
                                if (Seed.VariantIndex < 0 || Seed.VariantIndex >= static_cast<int>(Def.Variants.size()))
                                {
                                        OutError = "seed variant index out of range on " + Def.Id; return false;
                                }
                                Def.Seeds.push_back(Seed);
                        }
                }
                RumorDefs[Def.Id] = Def;
        }
        if (static_cast<int>(RumorDefs.size()) > RulesCfg.MaxActiveRumors)
        {
                OutError = "rumor data defines " + std::to_string(RumorDefs.size()) + " rumors - the cap is "
                        + std::to_string(RulesCfg.MaxActiveRumors) + " (NPC_SIMULATION 11: readability)";
                return false;
        }
        return true;
}

// ------------------------------------------------------------ seeding

void RumorSystem::ActivateDue(int Day)
{
        for (const auto& KV : RumorDefs)
        {
                if (KV.second.DayCreated == Day) { SeedRumor(KV.second); }
        }
}

void RumorSystem::SeedRumor(const RumorDef& Def)
{
        // Register every witness seed exactly once - re-seeding an event must not
        // duplicate knowledge or transmissions.
        for (const RumorSeed& Seed : Def.Seeds)
        {
                std::map<std::string, RumorKnowledge>& Mine = Knowledge[Seed.NpcId];
                if (Mine.count(Def.Id)) { continue; }   // already knows - no duplicate event
                RumorKnowledge K;
                K.RumorId = Def.Id;
                K.Kind = Seed.Kind;
                K.HopCount = 0;
                K.Confidence = std::min(Seed.Confidence, Def.OriginConfidence);
                K.Day = Def.DayCreated;
                K.Hour = Def.HourCreated;
                K.FromNpc.clear();
                K.WhereZone = Def.PlaceZone;
                K.VariantIndex = Seed.VariantIndex;
                Mine[Def.Id] = K;
        }
}

bool RumorSystem::RegisterWitnessEvent(const std::string& RumorId, int Day, int Hour, const std::string& Zone,
        const std::vector<std::string>& WitnessNpcIds, std::string& OutError)
{
        const RumorDef* Def = FindDef(RumorId);
        if (!Def) { OutError = "unknown rumor " + RumorId; return false; }
        if (Zone.empty()) { OutError = "witness event needs a zone"; return false; }

        // build an effective def copy with these witnesses as direct seeds
        std::set<std::string>& Logged = WitnessLog[RumorId];
        RumorDef EventDef = *Def;
        EventDef.DayCreated = Day;
        EventDef.HourCreated = Hour;
        EventDef.PlaceZone = Zone;
        EventDef.Seeds.clear();
        for (const std::string& Npc : WitnessNpcIds)
        {
                if (Logged.count(Npc)) { continue; }        // same event, same witness: ignore
                Logged.insert(Npc);
                RumorSeed Seed;
                Seed.NpcId = Npc;
                Seed.Kind = ETestimonyKind::Direct;
                Seed.Confidence = Def->OriginConfidence;
                EventDef.Seeds.push_back(Seed);
        }
        if (!EventDef.Seeds.empty()) { SeedRumor(EventDef); }
        return true;
}

// ------------------------------------------------------------ ticking

bool RumorSystem::AlreadyTransmitted(const std::string& RumorId, const std::string& From, const std::string& To,
        int Day, int Hour) const
{
        for (const RumorTransmission& T : Transmissions)
        {
                if (T.RumorId == RumorId && T.FromNpc == From && T.ToNpc == To && T.Day == Day && T.Hour == Hour)
                {
                        return true;
                }
        }
        return false;
}

bool RumorSystem::IsGossipZone(const std::string& Zone) const
{
        return GossipZones.count(Zone) != 0;
}

double RumorSystem::Relationship(const std::string& A, const std::string& B) const
{
        auto ItA = Relationships.find(A);
        if (ItA == Relationships.end()) { return 0.0; }
        auto ItB = ItA->second.find(B);
        return ItB == ItA->second.end() ? 0.0 : ItB->second;
}

RumorSystem::TickResult RumorSystem::TickHour(int Day, int Hour, const VillageState& Village, Rng& Rng)
{
        TickResult Result;

        // group rumor-capable NPCs by their current gossip zone
        std::map<std::string, std::vector<std::string>> ZoneOccupants;
        const auto& Npcs = Village.Npcs();
        for (const auto& KV : Npcs)
        {
                const std::string& NpcId = KV.first;
                const std::string Zone = Village.NpcZoneAt(NpcId, Hour);
                if (!IsGossipZone(Zone)) { continue; }
                ZoneOccupants[Zone].push_back(NpcId);
        }

        const int Population = static_cast<int>(Npcs.size());
        const int DailyCap = std::max(1, static_cast<int>(std::floor(RulesCfg.DailySpreadCap * Population)));
        // The spread cap is a DAILY budget (NPC_SIMULATION 10: <= 30% of the
        // population per day) - it must survive across the day's hourly ticks.
        int AlreadyToday = 0;
        if (const auto It = NewKnowersPerDay.find(Day); It != NewKnowersPerDay.end()) { AlreadyToday = It->second; }
        if (AlreadyToday >= DailyCap) { Result.bDailyCapReached = true; }

        // deterministic order: zones sorted (map), occupants sorted
        for (auto& ZoneKV : ZoneOccupants)
        {
                const std::string& Zone = ZoneKV.first;
                std::vector<std::string>& Present = ZoneKV.second;
                std::sort(Present.begin(), Present.end());

                for (const std::string& Speaker : Present)
                {
                        const std::map<std::string, RumorKnowledge>* SpeakerKnows = nullptr;
                        auto SKIt = Knowledge.find(Speaker);
                        if (SKIt != Knowledge.end()) { SpeakerKnows = &SKIt->second; }
                        if (!SpeakerKnows || SpeakerKnows->empty()) { continue; }

                        // hourly budget: count of rumors this speaker told this hour
                        int ToldThisHour = 0;
                        for (const RumorTransmission& T : Transmissions)
                        {
                                if (T.FromNpc == Speaker && T.Day == Day && T.Hour == Hour) { ++ToldThisHour; }
                        }
                        const std::string DailyKey = std::to_string(Day) + "|" + Speaker;
                        if (SpeakerDailyCount[DailyKey] >= RulesCfg.SpeakerDailyBudget) { continue; }

                        // listeners in the same zone, other than the speaker
                        for (const std::string& Listener : Present)
                        {
                                if (Listener == Speaker) { continue; }
                                if (ToldThisHour >= RulesCfg.SpeakerHourlyBudget) { break; }
                                if (SpeakerDailyCount[DailyKey] >= RulesCfg.SpeakerDailyBudget) { break; }
                                if (Result.bDailyCapReached) { break; }

                                const std::map<std::string, RumorKnowledge>* ListenerKnows = nullptr;
                                auto LKIt = Knowledge.find(Listener);
                                if (LKIt != Knowledge.end()) { ListenerKnows = &LKIt->second; }

                                for (const auto& RKV : *SpeakerKnows)
                                {
                                        if (ToldThisHour >= RulesCfg.SpeakerHourlyBudget) { break; }
                                        if (Result.bDailyCapReached) { break; }
                                        const RumorKnowledge& K = RKV.second;
                                        if (ListenerKnows && ListenerKnows->count(RKV.first)) { continue; }   // already knows

                                        // reticence: tension makes villages quieter (data trait + tension)
                                        const NPCDef* SpeakerDef = Village.FindNpc(Speaker);
                                        const double Reticence = SpeakerDef ? SpeakerDef->Reticence : 0.0;
                                        const double Effective = Reticence + Village.Tension() * 0.05;
                                        if (Effective >= RulesCfg.ReticenceBlock) { break; }   // this speaker is mute today

                                        // relationship gate: no gossip between estranged villagers
                                        if (Relationship(Speaker, Listener) < 0.0) { continue; }

                                        // bad rumors about Edmund travel slower through friendly mouths
                                        const RumorDef* Def = FindDef(RKV.first);
                                        double Chance = RulesCfg.BaseChance;
                                        if (Def && Def->Subject == "EDMUND" && Def->Valence < 0.0)
                                        {
                                                const double Trust = Village.GetTrust(Speaker);
                                                Chance *= 1.0 - std::max(0.0, Trust) / 200.0;
                                        }
                                        // a public denial dulls the day's gossip (NPC_SIMULATION 5)
                                        if (Day == LastDenialDay) { Chance *= 0.5; }
                                        // relationship warmth helps
                                        Chance *= 1.0 + Relationship(Speaker, Listener) / 200.0;
                                        if (!Rng.Chance(Chance)) { continue; }

                                        // no duplicate recording of the same transfer event
                                        if (AlreadyTransmitted(RKV.first, Speaker, Listener, Day, Hour)) { continue; }

                                        // --- the transfer happens ---
                                        // build the receiver's knowledge FIRST (mutation roll
                                        // included) so the transmission log records the wording
                                        // that was actually told, not the speaker's old one
                                        RumorKnowledge NewK;
                                        NewK.RumorId = RKV.first;
                                        NewK.Kind = ETestimonyKind::Hearsay;
                                        NewK.HopCount = K.HopCount + 1;
                                        NewK.Confidence = std::max(0.0, std::min(1.0, K.Confidence * RulesCfg.HopConfidence));
                                        NewK.Day = Day;
                                        NewK.Hour = Hour;
                                        NewK.FromNpc = Speaker;
                                        NewK.WhereZone = Zone;
                                        NewK.VariantIndex = K.VariantIndex;
                                        if (Rng.Chance(RulesCfg.MutationChance))
                                        {
                                                const RumorDef* RD = FindDef(RKV.first);
                                                if (RD && NewK.VariantIndex + 1 < static_cast<int>(RD->Variants.size()))
                                                {
                                                        ++NewK.VariantIndex;
                                                }
                                        }

                                        RumorTransmission T;
                                        T.RumorId = RKV.first;
                                        T.FromNpc = Speaker;
                                        T.ToNpc = Listener;
                                        T.Day = Day;
                                        T.Hour = Hour;
                                        T.Zone = Zone;
                                        T.VariantIndex = NewK.VariantIndex;
                                        Transmissions.push_back(T);
                                        ++ToldThisHour;
                                        ++SpeakerDailyCount[DailyKey];

                                        Knowledge[Listener][RKV.first] = NewK;
                                        Result.NewTransmissions.push_back(T);
                                        ++Result.NewKnowersToday;

                                        // first-spread tension event, once per rumor ever
                                        if (Def && Def->TensionOnSpread != 0.0 && !FirstSpreadDone.count(RKV.first))
                                        {
                                                FirstSpreadDone.insert(RKV.first);
                                                Result.RumorsThatFirstSpread.push_back(RKV.first);
                                        }

                                        NewKnowersPerDay[Day] = AlreadyToday + Result.NewKnowersToday;
                                        if (NewKnowersPerDay[Day] >= DailyCap) { Result.bDailyCapReached = true; }
                                        break;   // one rumor per listener per speaker per hour
                                }
                        }
                }
        }
        return Result;
}

void RumorSystem::ApplyDailyDecay(int Day)
{
        (void)Day;
        for (auto& NpcKV : Knowledge)
        {
                for (auto It = NpcKV.second.begin(); It != NpcKV.second.end();)
                {
                        const RumorDef* Def = FindDef(It->first);
                        const double Decay = Def ? Def->Decay : 0.25;
                        It->second.Confidence *= (1.0 - Decay);
                        if (It->second.Confidence < RulesCfg.ForgetBelow)
                        {
                                It = NpcKV.second.erase(It);   // rumor fades from memory
                        }
                        else
                        {
                                ++It;
                        }
                }
        }
}

int RumorSystem::NotifyPlayerLeak(const std::string& RumorId, int Day, int Hour, const std::string& Zone,
        const VillageState& Village, std::string& OutError)
{
        if (!FindDef(RumorId)) { OutError = "unknown rumor " + RumorId; return -1; }
        if (!IsGossipZone(Zone)) { OutError = "leak zone is not a gossip zone: " + Zone; return -1; }

        int Count = 0;
        const auto& Npcs = Village.Npcs();
        for (const auto& KV : Npcs)
        {
                const std::string& NpcId = KV.first;
                if (Village.NpcZoneAt(NpcId, Hour) != Zone) { continue; }        // must be present to hear
                if (Knowledge[NpcId].count(RumorId)) { continue; }               // already knows
                if (AlreadyTransmitted(RumorId, "PLAYER", NpcId, Day, Hour)) { continue; }

                RumorTransmission T;
                T.RumorId = RumorId;
                T.FromNpc = "PLAYER";
                T.ToNpc = NpcId;
                T.Day = Day;
                T.Hour = Hour;
                T.Zone = Zone;
                T.VariantIndex = 0;
                Transmissions.push_back(T);

                RumorKnowledge K;
                K.RumorId = RumorId;
                K.Kind = ETestimonyKind::Hearsay;       // anonymous word - never direct testimony
                K.HopCount = 1;
                K.Confidence = 0.55;                    // unattributed source caps confidence
                K.Day = Day;
                K.Hour = Hour;
                K.FromNpc = "PLAYER";
                K.WhereZone = Zone;
                K.VariantIndex = 0;
                Knowledge[NpcId][RumorId] = K;
                ++Count;
        }
        return Count;
}

// ------------------------------------------------------------ player tools

bool RumorSystem::NotifyPlayerHeard(const std::string& RumorId, int Day, int Hour, const std::string& FromNpc)
{
        if (!FindDef(RumorId)) { return false; }
        for (const std::string& K : PlayerKnown)
        {
                if (K == RumorId) { return true; }   // already known - no duplicate entry
        }
        PlayerKnown.push_back(RumorId);
        (void)Day; (void)Hour; (void)FromNpc;
        return true;
}

int RumorSystem::NotifyPlayerDenial(int Day, int Hour)
{
        (void)Hour;
        LastDenialDay = Day;   // gossip is dulled for the rest of this day
        int Affected = 0;
        for (auto& NpcKV : Knowledge)
        {
                for (auto& RKV : NpcKV.second)
                {
                        RKV.second.Confidence = std::max(0.0, RKV.second.Confidence - 0.30);
                        ++Affected;
                }
        }
        return Affected;
}

// ------------------------------------------------------------ queries

const RumorKnowledge* RumorSystem::NpcKnowledge(const std::string& NpcId, const std::string& RumorId) const
{
        auto It = Knowledge.find(NpcId);
        if (It == Knowledge.end()) { return nullptr; }
        auto KIt = It->second.find(RumorId);
        return KIt == It->second.end() ? nullptr : &KIt->second;
}

bool RumorSystem::NpcKnows(const std::string& NpcId, const std::string& RumorId) const
{
        return NpcKnowledge(NpcId, RumorId) != nullptr;
}

ETestimonyKind RumorSystem::NpcEffectiveKind(const std::string& NpcId, const std::string& RumorId) const
{
        const RumorKnowledge* K = NpcKnowledge(NpcId, RumorId);
        if (!K) { return ETestimonyKind::Unverified; }   // knows nothing: the weakest claim
        if (K->Kind == ETestimonyKind::Hearsay)
        {
                if (K->Confidence < 0.40 || K->VariantIndex >= 2) { return ETestimonyKind::Unverified; }
        }
        return K->Kind;
}

std::vector<std::string> RumorSystem::NpcsKnowing(const std::string& RumorId) const
{
        std::vector<std::string> Out;
        for (const auto& KV : Knowledge)
        {
                if (KV.second.count(RumorId)) { Out.push_back(KV.first); }
        }
        return Out;
}

int RumorSystem::KnowerCount(const std::string& RumorId) const
{
        return static_cast<int>(NpcsKnowing(RumorId).size());
}

std::vector<std::string> RumorSystem::ActiveRumorIds() const
{
        std::vector<std::string> Out;
        for (const auto& KV : RumorDefs)
        {
                if (KnowerCount(KV.first) > 0) { Out.push_back(KV.first); }
        }
        return Out;
}

std::vector<RumorSystem::RumorConflict> RumorSystem::FindConflicts(const std::string& NpcId) const
{
        std::vector<RumorConflict> Out;
        auto It = Knowledge.find(NpcId);
        if (It == Knowledge.end()) { return Out; }
        for (const auto& A : It->second)
        {
                for (const auto& B : It->second)
                {
                        if (A.first >= B.first) { continue; }
                        const RumorDef* DA = FindDef(A.first);
                        const RumorDef* DB = FindDef(B.first);
                        if (!DA || !DB) { continue; }
                        if (DA->Topic != DB->Topic) { continue; }
                        if ((DA->Valence < 0.0 && DB->Valence > 0.0) || (DA->Valence > 0.0 && DB->Valence < 0.0))
                        {
                                RumorConflict C;
                                C.RumorA = A.first;
                                C.RumorB = B.first;
                                C.Topic = DA->Topic;
                                Out.push_back(C);
                        }
                }
        }
        return Out;
}

std::vector<RumorTransmission> RumorSystem::TraceProvenance(const std::string& RumorId, const std::string& NpcId) const
{
        // walk backwards from the holder through the transmission log
        std::vector<RumorTransmission> Chain;   // built reversed, then flipped
        std::string Cursor = NpcId;
        std::set<std::string> Visited;
        while (true)
        {
                if (Visited.count(Cursor)) { break; }   // cycle guard (should never trigger)
                Visited.insert(Cursor);
                const RumorTransmission* Step = nullptr;
                for (const RumorTransmission& T : Transmissions)
                {
                        if (T.RumorId == RumorId && T.ToNpc == Cursor) { Step = &T; }   // last match wins
                }
                if (!Step) { break; }   // reached origin/direct knowledge
                Chain.push_back(*Step);
                Cursor = Step->FromNpc;
                if (Cursor.empty()) { break; }
        }
        std::reverse(Chain.begin(), Chain.end());
        return Chain;
}

const RumorDef* RumorSystem::FindDef(const std::string& RumorId) const
{
        auto It = RumorDefs.find(RumorId);
        return It == RumorDefs.end() ? nullptr : &It->second;
}

// ------------------------------------------------------------ save / load

JsonValue RumorSystem::SerializeState() const
{
        JsonValue Root = JsonValue::MakeObject();

        JsonValue Know = JsonValue::MakeObject();
        for (const auto& NpcKV : Knowledge)
        {
                JsonValue Arr = JsonValue::MakeArray();
                for (const auto& RKV : NpcKV.second)
                {
                        const RumorKnowledge& K = RKV.second;
                        JsonValue J = JsonValue::MakeObject();
                        J.Set("rumor", JsonValue(K.RumorId));
                        J.Set("kind", JsonValue(std::string(ToString(K.Kind))));
                        J.Set("hops", JsonValue(K.HopCount));
                        J.Set("confidence", JsonValue(K.Confidence));
                        J.Set("day", JsonValue(K.Day));
                        J.Set("hour", JsonValue(K.Hour));
                        J.Set("from", JsonValue(K.FromNpc));
                        J.Set("zone", JsonValue(K.WhereZone));
                        J.Set("variant", JsonValue(K.VariantIndex));
                        Arr.Append(std::move(J));
                }
                Know.Set(NpcKV.first, std::move(Arr));
        }
        Root.Set("knowledge", std::move(Know));

        JsonValue Trans = JsonValue::MakeArray();
        for (const RumorTransmission& T : Transmissions)
        {
                JsonValue J = JsonValue::MakeObject();
                J.Set("rumor", JsonValue(T.RumorId));
                J.Set("from", JsonValue(T.FromNpc));
                J.Set("to", JsonValue(T.ToNpc));
                J.Set("day", JsonValue(T.Day));
                J.Set("hour", JsonValue(T.Hour));
                J.Set("zone", JsonValue(T.Zone));
                J.Set("variant", JsonValue(T.VariantIndex));
                Trans.Append(std::move(J));
        }
        Root.Set("transmissions", std::move(Trans));

        JsonValue PL = JsonValue::MakeArray();
        for (const std::string& R : PlayerKnown) { PL.Append(JsonValue(R)); }
        Root.Set("player_known", std::move(PL));

        JsonValue FS = JsonValue::MakeArray();
        for (const std::string& R : FirstSpreadDone) { FS.Append(JsonValue(R)); }
        Root.Set("first_spread_done", std::move(FS));

        JsonValue WL = JsonValue::MakeObject();
        for (const auto& KV : WitnessLog)
        {
                JsonValue Arr = JsonValue::MakeArray();
                for (const std::string& W : KV.second) { Arr.Append(JsonValue(W)); }
                WL.Set(KV.first, std::move(Arr));
        }
        Root.Set("witness_log", std::move(WL));

        JsonValue KD = JsonValue::MakeObject();
        for (const auto& KV : NewKnowersPerDay) { KD.Set(std::to_string(KV.first), JsonValue(KV.second)); }
        Root.Set("knowers_by_day", std::move(KD));
        Root.Set("last_denial_day", JsonValue(LastDenialDay));

        return Root;
}

bool RumorSystem::DeserializeState(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "rumor state root not an object"; return false; }

        // validate everything first, then commit - a rejected load leaves no mess
        std::map<std::string, std::map<std::string, RumorKnowledge>> NewKnowledge;
        if (const JsonValue* Know = Root.Find("knowledge"))
        {
                if (!Know->IsObject()) { OutError = "knowledge not an object"; return false; }
                for (const auto& NpcKV : Know->AsObject())
                {
                        if (!NpcKV.second.IsArray()) { OutError = "knowledge entry not an array"; return false; }
                        for (size_t I = 0; I < NpcKV.second.Size(); ++I)
                        {
                                const JsonValue* J = NpcKV.second.At(I);
                                if (!J || !J->IsObject()) { OutError = "knowledge item not an object"; return false; }
                                RumorKnowledge K;
                                K.RumorId = J->GetString("rumor", "");
                                if (!FindDef(K.RumorId)) { OutError = "knowledge references unknown rumor " + K.RumorId; return false; }
                                std::string KindStr = J->GetString("kind", "hearsay");
                                if (!ParseTestimonyKind(KindStr, K.Kind)) { OutError = "bad kind in knowledge"; return false; }
                                K.HopCount = J->GetInt("hops", 0);
                                K.Confidence = J->GetNumber("confidence", 1.0);
                                if (K.Confidence < 0.0 || K.Confidence > 1.0) { OutError = "confidence out of range"; return false; }
                                K.Day = J->GetInt("day", 1);
                                K.Hour = J->GetInt("hour", 8);
                                if (K.Day < 1 || K.Day > 9 || K.Hour < 0 || K.Hour > 23) { OutError = "knowledge day/hour out of range"; return false; }
                                K.FromNpc = J->GetString("from", "");
                                K.WhereZone = J->GetString("zone", "");
                                K.VariantIndex = J->GetInt("variant", 0);
                                const RumorDef* Def = FindDef(K.RumorId);
                                if (K.VariantIndex < 0 || K.VariantIndex >= static_cast<int>(Def->Variants.size()))
                                {
                                        OutError = "variant index out of range in knowledge"; return false;
                                }
                                NewKnowledge[NpcKV.first][K.RumorId] = K;
                        }
                }
        }

        std::vector<RumorTransmission> NewTrans;
        if (const JsonValue* Trans = Root.Find("transmissions"))
        {
                if (!Trans->IsArray()) { OutError = "transmissions not an array"; return false; }
                for (size_t I = 0; I < Trans->Size(); ++I)
                {
                        const JsonValue* J = Trans->At(I);
                        if (!J || !J->IsObject()) { OutError = "transmission item not an object"; return false; }
                        RumorTransmission T;
                        T.RumorId = J->GetString("rumor", "");
                        if (!FindDef(T.RumorId)) { OutError = "transmission references unknown rumor " + T.RumorId; return false; }
                        T.FromNpc = J->GetString("from", "");
                        T.ToNpc = J->GetString("to", "");
                        T.Day = J->GetInt("day", 1);
                        T.Hour = J->GetInt("hour", 8);
                        if (T.Day < 1 || T.Day > 9 || T.Hour < 0 || T.Hour > 23) { OutError = "transmission day/hour out of range"; return false; }
                        T.Zone = J->GetString("zone", "");
                        T.VariantIndex = J->GetInt("variant", 0);
                        NewTrans.push_back(T);
                }
        }

        std::vector<std::string> NewPlayerKnown;
        if (const JsonValue* PL = Root.Find("player_known"))
        {
                if (!PL->IsArray()) { OutError = "player_known not an array"; return false; }
                for (size_t I = 0; I < PL->Size(); ++I)
                {
                        const JsonValue* J = PL->At(I);
                        if (!J || !J->IsString()) { OutError = "player_known item not a string"; return false; }
                        const std::string R = J->AsString();
                        if (!FindDef(R)) { OutError = "player_known references unknown rumor " + R; return false; }
                        NewPlayerKnown.push_back(R);
                }
        }

        std::set<std::string> NewFS;
        if (const JsonValue* FS = Root.Find("first_spread_done"))
        {
                for (size_t I = 0; I < FS->Size(); ++I)
                {
                        if (const JsonValue* J = FS->At(I))
                        {
                                if (!FindDef(J->AsString())) { OutError = "first_spread_done references unknown rumor"; return false; }
                                NewFS.insert(J->AsString());
                        }
                }
        }

        std::map<std::string, std::set<std::string>> NewWL;
        if (const JsonValue* WL = Root.Find("witness_log"))
        {
                if (!WL->IsObject()) { OutError = "witness_log not an object"; return false; }
                for (const auto& KV : WL->AsObject())
                {
                        if (!KV.second.IsArray()) { OutError = "witness_log entry not an array"; return false; }
                        std::set<std::string> W;
                        for (size_t I = 0; I < KV.second.Size(); ++I)
                        {
                                if (const JsonValue* J = KV.second.At(I)) { W.insert(J->AsString()); }
                        }
                        NewWL[KV.first] = W;
                }
        }

        std::map<int, int> NewKD;
        if (const JsonValue* KD = Root.Find("knowers_by_day"))
        {
                if (!KD->IsObject()) { OutError = "knowers_by_day not an object"; return false; }
                for (const auto& KV : KD->AsObject())
                {
                        const int Day = std::atoi(KV.first.c_str());
                        const int Count = KV.second.AsInt();
                        if (Day < 1 || Day > 9 || Count < 0) { OutError = "knowers_by_day entry out of range"; return false; }
                        NewKD[Day] = Count;
                }
        }

        int NewDenialDay = -1;
        if (const JsonValue* DD = Root.Find("last_denial_day"))
        {
                NewDenialDay = DD->AsInt();
                if (NewDenialDay < -1 || NewDenialDay > 9) { OutError = "last_denial_day out of range"; return false; }
        }

        // commit
        Knowledge = std::move(NewKnowledge);
        Transmissions = std::move(NewTrans);
        PlayerKnown = std::move(NewPlayerKnown);
        FirstSpreadDone = std::move(NewFS);
        WitnessLog = std::move(NewWL);
        NewKnowersPerDay = std::move(NewKD);
        LastDenialDay = NewDenialDay;
        SpeakerDailyCount.clear();
        return true;
}

} // namespace tls
