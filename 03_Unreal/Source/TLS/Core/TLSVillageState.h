// THE LAST SIN: The Sin-Eater - M1
// TLSVillageState: village-level simulation state - per-NPC trust with tone
// weights and relationship bias, faction spillover, reputation, tension,
// day/time/weather script and NPC daily schedules.
// Semantics per docs/NPC_SIMULATION.md 3 (Trust/Reputation) and 7 (schedules).

#pragma once

#include "TLSCoreTypes.h"
#include "TLSJson.h"

#include <map>
#include <string>
#include <vector>

namespace tls
{

class VillageState
{
public:
        bool Load(const JsonValue& Root, std::string& OutError);

        // ---- day / time / weather ----
        // Restores the day-1 script, initial trust and zero reputation (NewGame).
        void ResetToDayOne();
        int Day() const { return CurrentDay; }
        int Hour() const { return CurrentHour; }
        ETimeOfDay TimeOfDay() const { return CurrentTime; }
        EWeather Weather() const { return CurrentWeather; }
        double Tension() const { return TensionLevel; }        // 0..5
        double Reputation() const { return ReputationValue; }  // -100..100

        void BeginDay(int NewDay);
        void AdvanceHour(int Hours);
        void SetTimeOfDay(ETimeOfDay T);
        bool AdvanceToEvening();   // returns true when the day's evening is reached

        // ---- trust ----
        double GetTrust(const std::string& NpcId) const;
        // Applies (raw + toneWeight) * (1 - bias), clamps, then faction spillover.
        // Returns the final applied delta for the source NPC.
        double ApplyTrustDelta(const std::string& NpcId, double RawDelta, ETone Tone,
                std::vector<std::string>* OutSpilloverLog = nullptr);
        void ApplyReputationDelta(double Delta) { ReputationValue += Delta; ClampReputation(); }
        void ApplyTensionDelta(double Delta) { TensionLevel += Delta; ClampTension(); }

        // ---- npcs / schedules ----
        const NPCDef* FindNpc(const std::string& Id) const;
        const std::map<std::string, NPCDef>& Npcs() const { return NpcDefs; }
        // Returns the zone (area id) where the NPC stands at the given hour.
        std::string NpcZoneAt(const std::string& NpcId, int Hour) const;
        int CountBackgroundNpcs() const;   // tier 3 - M1 scope wants 12 with schedules

        // ---- save / load ----
        JsonValue SerializeState() const;
        bool DeserializeState(const JsonValue& Root, std::string& OutError);

private:
        void ClampReputation() { if (ReputationValue > 100.0) { ReputationValue = 100.0; } if (ReputationValue < -100.0) { ReputationValue = -100.0; } }
        void ClampTension() { if (TensionLevel > 5.0) { TensionLevel = 5.0; } if (TensionLevel < 0.0) { TensionLevel = 0.0; } }
        ETimeOfDay HourToTime(int Hour) const;

        int CurrentDay = 1;
        int CurrentHour = 8;
        ETimeOfDay CurrentTime = ETimeOfDay::Morning;
        EWeather CurrentWeather = EWeather::OvercastFog;
        double TensionLevel = 1.0;
        double ReputationValue = 0.0;

        std::map<std::string, NPCDef> NpcDefs;
        std::map<std::string, double> Trust;                 // npc id -> current trust
        std::map<std::string, std::map<std::string, double>> Spillover; // faction -> faction -> factor
        std::map<int, std::string> WeatherByDay;             // day -> weather key
        std::map<int, double> TensionByDay;                  // day -> tension floor on begin
};

} // namespace tls
