// THE LAST SIN: The Sin-Eater - M2
// bench_sim: reproducible performance measurement of the core simulation.
// Measures the engine-free gossip tick (RumorSystem::TickHour) and full-day
// advancement on the REAL 17-NPC village data. This is the algorithmic cost
// only - the UE frame budget (<1.5 ms per NPC_SIMULATION 10) needs a live
// UE measurement and is NOT claimed here.
//
// Build: tools/bench_sim.sh (g++ -O1, same flags as the test suite)
// Run from the repo root.

#include "TLSJson.h"
#include "TLSCoreTypes.h"
#include "TLSRumors.h"
#include "TLSRng.h"
#include "TLSVillageState.h"
#include "TLSSettings.h"

#include <chrono>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>

using namespace tls;

static std::string Slurp(const char* Path)
{
        std::ifstream F(Path);
        std::stringstream S;
        S << F.rdbuf();
        return S.str();
}

int main()
{
        std::string Err;
        auto V = std::make_unique<VillageState>();
        if (!V->Load(JsonParse(Slurp("05_Narrative/sim/sim_blackthorne.json")).Value, Err))
        {
                std::printf("FATAL: sim data: %s\n", Err.c_str());
                return 2;
        }
        auto R = std::make_unique<RumorSystem>();
        if (!R->Load(JsonParse(Slurp("05_Narrative/rumors/rumors_blackthorne.json")).Value, Err))
        {
                std::printf("FATAL: rumor data: %s\n", Err.c_str());
                return 2;
        }
        R->ActivateDue(1);

        const int Population = static_cast<int>(V->Npcs().size());
        std::printf("TLS core simulation benchmark\n");
        std::printf("village population : %d NPCs\n", Population);
        std::printf("rumors in data     : %d\n", static_cast<int>(R->Defs().size()));
        std::printf("build flags        : g++ -O1 (same as the CI test suite)\n");

        // ---- warmup ----
        Rng Warm(1);
        for (int Hour = 8; Hour <= 21; ++Hour) { R->TickHour(1, Hour, *V, Warm); }

        // ---- per-tick cost: 14 gossip hours/day over 30 simulated days ----
        Rng Rng(42);
        const int Days = 30;
        auto T0 = std::chrono::steady_clock::now();
        long Ticks = 0, Transfers = 0;
        for (int Day = 1; Day <= Days; ++Day)
        {
                for (int Hour = 8; Hour <= 21; ++Hour)
                {
                        auto Result = R->TickHour(Day, Hour, *V, Rng);
                        Transfers += static_cast<long>(Result.NewTransmissions.size());
                        ++Ticks;
                }
                R->ApplyDailyDecay(Day);
                R->ActivateDue(Day);
        }
        auto T1 = std::chrono::steady_clock::now();
        const double TotalUs = std::chrono::duration<double, std::micro>(T1 - T0).count();
        std::printf("\n-- gossip tick (%d NPCs, %d rumors) --\n", Population, static_cast<int>(R->Defs().size()));
        std::printf("ticks executed        : %ld (14/day x %d days)\n", Ticks, Days);
        std::printf("transmissions created : %ld\n", Transfers);
        std::printf("total wall time       : %.0f us\n", TotalUs);
        std::printf("mean cost per tick    : %.2f us\n", TotalUs / Ticks);
        std::printf("mean cost per full day: %.2f us (14 ticks)\n", TotalUs / Days);

        // ---- context: a worst-case frame that spends the HIGH-tier budget
        //      (4 ticks) still sits far under the 1.5 ms frame budget if the
        //      mean tick stays in the tens of microseconds - the UE-side
        //      integration cost is separate and NOT measured here.
        SettingsModel S;
        S.SetQualityTier(EQualityTier::High);
        std::printf("\nhigh-tier frame spend (4 ticks x mean): %.2f us (core algorithm only)\n",
                4.0 * TotalUs / Ticks);
        std::printf("NOTE: the 1.5 ms UE frame budget (NPC_SIMULATION 10) requires a live\n");
        std::printf("UE 5.4 measurement - not claimed from this standalone result.\n");
        return 0;
}
