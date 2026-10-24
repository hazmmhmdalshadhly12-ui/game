// THE LAST SIN: The Sin-Eater - M1
// TLSVillageState.cpp

#include "TLSVillageState.h"

#include <algorithm>

namespace tls
{

namespace
{
        bool ParseSchedule(const JsonValue* Arr, std::vector<ScheduleSegment>& Out, const std::string& NpcId, std::string& OutError)
        {
                if (!Arr || !Arr->IsArray()) { OutError = "npc " + NpcId + " schedule missing"; return false; }
                for (size_t I = 0; I < Arr->Size(); ++I)
                {
                        const JsonValue* S = Arr->At(I);
                        if (!S || !S->IsObject()) { OutError = "npc " + NpcId + " schedule segment not an object"; return false; }
                        ScheduleSegment Seg;
                        Seg.FromHour = S->GetInt("from_hour", 0);
                        Seg.ToHour = S->GetInt("to_hour", 24);
                        Seg.Zone = S->GetString("zone", "");
                        Seg.Activity = S->GetString("activity", "");
                        Seg.Bark = S->GetString("bark", "");
                        if (Seg.Zone.empty()) { OutError = "npc " + NpcId + " schedule segment missing zone"; return false; }
                        if (Seg.FromHour < 0 || Seg.FromHour > 24 || Seg.ToHour < 0 || Seg.ToHour > 24 || Seg.FromHour >= Seg.ToHour)
                        {
                                OutError = "npc " + NpcId + " schedule segment has invalid hour range";
                                return false;
                        }
                        Out.push_back(Seg);
                }
                return true;
        }
}

bool VillageState::Load(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "sim root must be an object"; return false; }

        const JsonValue* Npcs = Root.Find("npcs");
        if (!Npcs || !Npcs->IsArray() || Npcs->Size() == 0) { OutError = "missing 'npcs' array"; return false; }
        for (size_t I = 0; I < Npcs->Size(); ++I)
        {
                const JsonValue* N = Npcs->At(I);
                if (!N || !N->IsObject()) { OutError = "npc entry not an object"; return false; }
                NPCDef Def;
                Def.Id = N->GetString("id", "");
                Def.Name = N->GetString("name", "");
                Def.Tier = N->GetInt("tier", 3);
                Def.Faction = N->GetString("faction", "none");
                Def.InitialTrust = N->GetNumber("initial_trust", 0.0);
                Def.RelationshipBias = N->GetNumber("relationship_bias", 0.0);
                Def.VisualFamily = N->GetString("visual_family", "T3");
                Def.Reticence = N->GetNumber("reticence", 0.0);
                if (Def.Id.empty()) { OutError = "npc missing id"; return false; }
                if (Def.InitialTrust < -100.0 || Def.InitialTrust > 100.0) { OutError = "npc " + Def.Id + " trust out of range"; return false; }
                if (Def.RelationshipBias < 0.0 || Def.RelationshipBias > 1.0) { OutError = "npc " + Def.Id + " bias out of range"; return false; }
                if (Def.Reticence < 0.0 || Def.Reticence > 1.0) { OutError = "npc " + Def.Id + " reticence out of range"; return false; }

                if (const JsonValue* Tw = N->Find("tone_weights"))
                {
                        for (const auto& KV : Tw->AsObject())
                        {
                                ETone Tone;
                                if (!ParseTone(KV.first, Tone)) { OutError = "npc " + Def.Id + " bad tone key '" + KV.first + "'"; return false; }
                                Def.ToneWeights[Tone] = KV.second.AsNumber(0.0);
                        }
                }

                if (!ParseSchedule(N->Find("schedule"), Def.Schedule, Def.Id, OutError)) { return false; }
                if (const JsonValue* Tn = N->Find("schedule_tension"))
                {
                        if (!ParseSchedule(Tn, Def.ScheduleTension, Def.Id, OutError)) { return false; }
                }

                NpcDefs[Def.Id] = Def;
                Trust[Def.Id] = Def.InitialTrust;
        }

        if (const JsonValue* Sp = Root.Find("faction_spillover"))
        {
                for (const auto& Src : Sp->AsObject())
                {
                        for (const auto& Dst : Src.second.AsObject())
                        {
                                Spillover[Src.first][Dst.first] = Dst.second.AsNumber(0.0);
                        }
                }
        }

        if (const JsonValue* Wd = Root.Find("weather_by_day"))
        {
                for (const auto& KV : Wd->AsObject())
                {
                        WeatherByDay[std::atoi(KV.first.c_str())] = KV.second.AsString();
                }
        }
        if (const JsonValue* Td = Root.Find("tension_by_day"))
        {
                for (const auto& KV : Td->AsObject())
                {
                        TensionByDay[std::atoi(KV.first.c_str())] = KV.second.AsNumber(1.0);
                }
        }

        // apply the day-1 script immediately
        CurrentDay = 1;
        CurrentHour = 8;
        CurrentTime = ETimeOfDay::Morning;
        auto W1 = WeatherByDay.find(1);
        if (W1 != WeatherByDay.end() && !ParseWeather(W1->second, CurrentWeather)) { OutError = "bad weather key for day 1"; return false; }
        auto T1 = TensionByDay.find(1);
        TensionLevel = T1 != TensionByDay.end() ? T1->second : 1.0;
        ClampTension();

        return true;
}

void VillageState::BeginDay(int NewDay)
{
        CurrentDay = NewDay;
        CurrentHour = 7;
        CurrentTime = ETimeOfDay::Morning;
        auto W = WeatherByDay.find(NewDay);
        if (W != WeatherByDay.end())
        {
                EWeather Parsed = CurrentWeather;
                if (ParseWeather(W->second, Parsed)) { CurrentWeather = Parsed; }
        }
        auto T = TensionByDay.find(NewDay);
        if (T != TensionByDay.end() && T->second > TensionLevel) { TensionLevel = T->second; }
        ClampTension();
}

void VillageState::ResetToDayOne()
{
        CurrentDay = 1;
        CurrentHour = 8;
        CurrentTime = ETimeOfDay::Morning;
        ReputationValue = 0.0;
        auto W = WeatherByDay.find(1);
        if (W != WeatherByDay.end())
        {
                EWeather Parsed = CurrentWeather;
                if (ParseWeather(W->second, Parsed)) { CurrentWeather = Parsed; }
        }
        auto T = TensionByDay.find(1);
        TensionLevel = T != TensionByDay.end() ? T->second : 1.0;
        ClampTension();
        Trust.clear();
        for (const auto& KV : NpcDefs) { Trust[KV.first] = KV.second.InitialTrust; }
}

ETimeOfDay VillageState::HourToTime(int Hour) const
{
        if (Hour < 12) { return ETimeOfDay::Morning; }
        if (Hour < 14) { return ETimeOfDay::Noon; }
        if (Hour < 18) { return ETimeOfDay::Afternoon; }
        if (Hour < 22) { return ETimeOfDay::Evening; }
        return ETimeOfDay::Night;
}

void VillageState::AdvanceHour(int Hours)
{
        CurrentHour += Hours;
        CurrentTime = HourToTime(CurrentHour);
}

void VillageState::SetTimeOfDay(ETimeOfDay T)
{
        CurrentTime = T;
        if (T == ETimeOfDay::Morning) { CurrentHour = std::max(CurrentHour, 8); }
        else if (T == ETimeOfDay::Noon) { CurrentHour = std::max(CurrentHour, 12); }
        else if (T == ETimeOfDay::Afternoon) { CurrentHour = std::max(CurrentHour, 14); }
        else if (T == ETimeOfDay::Evening) { CurrentHour = std::max(CurrentHour, 18); }
        else if (T == ETimeOfDay::Night) { CurrentHour = std::max(CurrentHour, 22); }
}

bool VillageState::AdvanceToEvening()
{
        if (CurrentTime == ETimeOfDay::Evening || CurrentTime == ETimeOfDay::Night) { return false; }
        SetTimeOfDay(ETimeOfDay::Evening);
        return true;
}

const NPCDef* VillageState::FindNpc(const std::string& Id) const
{
        auto It = NpcDefs.find(Id);
        return It == NpcDefs.end() ? nullptr : &It->second;
}

double VillageState::GetTrust(const std::string& NpcId) const
{
        auto It = Trust.find(NpcId);
        return It == Trust.end() ? 0.0 : It->second;
}

double VillageState::ApplyTrustDelta(const std::string& NpcId, double RawDelta, ETone Tone,
        std::vector<std::string>* OutSpilloverLog)
{
        auto It = NpcDefs.find(NpcId);
        if (It == NpcDefs.end()) { return 0.0; }
        const NPCDef& Def = It->second;

        double ToneBonus = 0.0;
        auto TW = Def.ToneWeights.find(Tone);
        if (TW != Def.ToneWeights.end()) { ToneBonus = TW->second; }

        // NPC_SIMULATION 3: every adjustment = delta * (1 - relationship_bias)
        double Final = (RawDelta + ToneBonus) * (1.0 - Def.RelationshipBias);
        if (Final == 0.0) { return 0.0; }

        double Before = Trust[NpcId];
        Trust[NpcId] = Before + Final;
        if (Trust[NpcId] > 100.0) { Trust[NpcId] = 100.0; }
        if (Trust[NpcId] < -100.0) { Trust[NpcId] = -100.0; }
        const double Applied = Trust[NpcId] - Before;

        // faction spillover: the same delta echoes (dampened) into rival factions
        if (Applied != 0.0)
        {
                auto Src = Spillover.find(Def.Faction);
                if (Src != Spillover.end())
                {
                        for (const auto& KV : Src->second)
                        {
                                const std::string& TargetFaction = KV.first;
                                const double Factor = KV.second;
                                if (Factor == 0.0) { continue; }
                                for (const auto& Np : NpcDefs)
                                {
                                        if (Np.second.Faction == TargetFaction && Np.first != NpcId)
                                        {
                                                double& T = Trust[Np.first];
                                                const double Before2 = T;
                                                T += Applied * Factor;
                                                if (T > 100.0) { T = 100.0; }
                                                if (T < -100.0) { T = -100.0; }
                                                if (OutSpilloverLog && T != Before2)
                                                {
                                                        OutSpilloverLog->push_back(Np.first + " " + std::string(T > Before2 ? "+" : "") + std::to_string(T - Before2));
                                                }
                                        }
                                }
                        }
                }
        }
        return Applied;
}

// M3.7: a non-dialogue event delta (an accusation, a public scene). Same path
// as ApplyTrustDelta but WITHOUT the tone weight - the village is not scoring
// a conversational tone here - while keeping bias, clamping and spillover.
double VillageState::ApplyTrustEvent(const std::string& NpcId, double RawDelta,
        std::vector<std::string>* OutSpilloverLog)
{
        auto It = NpcDefs.find(NpcId);
        if (It == NpcDefs.end()) { return 0.0; }
        const NPCDef& Def = It->second;

        double Final = RawDelta * (1.0 - Def.RelationshipBias);
        if (Final == 0.0) { return 0.0; }

        double Before = Trust[NpcId];
        Trust[NpcId] = Before + Final;
        if (Trust[NpcId] > 100.0) { Trust[NpcId] = 100.0; }
        if (Trust[NpcId] < -100.0) { Trust[NpcId] = -100.0; }
        const double Applied = Trust[NpcId] - Before;

        if (Applied != 0.0)
        {
                auto Src = Spillover.find(Def.Faction);
                if (Src != Spillover.end())
                {
                        for (const auto& KV : Src->second)
                        {
                                const std::string& TargetFaction = KV.first;
                                const double Factor = KV.second;
                                if (Factor == 0.0) { continue; }
                                for (const auto& Np : NpcDefs)
                                {
                                        if (Np.second.Faction == TargetFaction && Np.first != NpcId)
                                        {
                                                double& T = Trust[Np.first];
                                                const double Before2 = T;
                                                T += Applied * Factor;
                                                if (T > 100.0) { T = 100.0; }
                                                if (T < -100.0) { T = -100.0; }
                                                if (OutSpilloverLog && T != Before2)
                                                {
                                                        OutSpilloverLog->push_back(Np.first + " " + std::string(T > Before2 ? "+" : "") + std::to_string(T - Before2));
                                                }
                                        }
                                }
                        }
                }
        }
        return Applied;
}

std::string VillageState::NpcZoneAt(const std::string& NpcId, int Hour) const
{
        auto It = NpcDefs.find(NpcId);
        if (It == NpcDefs.end()) { return ""; }
        const NPCDef& Def = It->second;
        const std::vector<ScheduleSegment>& Segments = (TensionLevel >= 3.0 && !Def.ScheduleTension.empty()) ? Def.ScheduleTension : Def.Schedule;
        for (const ScheduleSegment& S : Segments)
        {
                if (Hour >= S.FromHour && Hour < S.ToHour) { return S.Zone; }
        }
        return Segments.empty() ? "" : Segments.back().Zone;
}

int VillageState::CountBackgroundNpcs() const
{
        int Count = 0;
        for (const auto& KV : NpcDefs)
        {
                if (KV.second.Tier == 3) { ++Count; }
        }
        return Count;
}

JsonValue VillageState::SerializeState() const
{
        JsonValue Root = JsonValue::MakeObject();
        Root.Set("day", JsonValue(CurrentDay));
        Root.Set("hour", JsonValue(CurrentHour));
        Root.Set("time", JsonValue(std::string(ToString(CurrentTime))));
        Root.Set("weather", JsonValue(std::string(ToString(CurrentWeather))));
        Root.Set("tension", JsonValue(TensionLevel));
        Root.Set("reputation", JsonValue(ReputationValue));
        JsonValue TrustArr = JsonValue::MakeArray();
        for (const auto& KV : Trust)
        {
                JsonValue T = JsonValue::MakeObject();
                T.Set("npc", JsonValue(KV.first));
                T.Set("value", JsonValue(KV.second));
                TrustArr.Append(std::move(T));
        }
        Root.Set("trust", std::move(TrustArr));
        return Root;
}

bool VillageState::DeserializeState(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "village state root not an object"; return false; }
        CurrentDay = Root.GetInt("day", 1);
        CurrentHour = Root.GetInt("hour", 8);
        if (CurrentDay < 1 || CurrentDay > 9) { OutError = "village day out of range"; return false; }
        if (CurrentHour < 0 || CurrentHour > 23) { OutError = "village hour out of range"; return false; }
        std::string TimeStr = Root.GetString("time", "morning");
        if (!ParseTimeOfDay(TimeStr, CurrentTime)) { OutError = "bad time key " + TimeStr; return false; }
        std::string WeatherStr = Root.GetString("weather", "overcast_fog");
        if (!ParseWeather(WeatherStr, CurrentWeather)) { OutError = "bad weather key " + WeatherStr; return false; }
        TensionLevel = Root.GetNumber("tension", 1.0);
        ReputationValue = Root.GetNumber("reputation", 0.0);
        ClampTension();
        ClampReputation();
        Trust.clear();
        for (const auto& KV : NpcDefs) { Trust[KV.first] = KV.second.InitialTrust; }
        if (const JsonValue* Arr = Root.Find("trust"))
        {
                if (!Arr->IsArray()) { OutError = "trust must be an array"; return false; }
                for (size_t I = 0; I < Arr->Size(); ++I)
                {
                        const JsonValue* T = Arr->At(I);
                        if (!T || !T->IsObject()) { OutError = "trust entry not an object"; return false; }
                        const std::string Npc = T->GetString("npc", "");
                        if (!Npc.empty() && !NpcDefs.count(Npc)) { OutError = "trust entry for unknown npc " + Npc; return false; }
                        const double Value = T->GetNumber("value", 0.0);
                        if (Value < -100.0 || Value > 100.0) { OutError = "trust value out of range for " + Npc; return false; }
                        if (!Npc.empty()) { Trust[Npc] = Value; }
                }
        }
        return true;
}

} // namespace tls
