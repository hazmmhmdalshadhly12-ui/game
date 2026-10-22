// THE LAST SIN: The Sin-Eater - M2.1
// test_rumors: rumor & witness engine tests.
// Covers the M2.1 acceptance list: credibility, testimony conflicts, spread,
// spread termination, source tracking, player tools, save/load and the
// 7-day headless village simulation (NPC_SIMULATION 10).

#include "tls_test_framework.h"
#include "TLSJson.h"
#include "TLSCoreTypes.h"
#include "TLSRumors.h"
#include "TLSRng.h"
#include "TLSVillageState.h"
#include "TLSGameState.h"

#include <cmath>
#include <memory>
#include <string>

using namespace tls;

namespace tls_test_rumors
{
void RunAll();
}

namespace
{

// ------------------------------------------------------------ fixtures

std::unique_ptr<RumorSystem> MakeRumors(const std::string& Json, std::string& Err)
{
        JsonParseResult P = JsonParse(Json);
        if (!P.Ok) { Err = "fixture json: " + P.Error; return nullptr; }
        auto Sys = std::make_unique<RumorSystem>();
        if (!Sys->Load(P.Value, Err)) { return nullptr; }
        Err.clear();
        return Sys;
}

std::unique_ptr<VillageState> MakeVillage(const std::string& Json, std::string& Err)
{
        JsonParseResult P = JsonParse(Json);
        if (!P.Ok) { Err = "fixture json: " + P.Error; return nullptr; }
        auto V = std::make_unique<VillageState>();
        if (!V->Load(P.Value, Err)) { return nullptr; }
        Err.clear();
        return V;
}

// three-person village: A and B share AREA-SQUARE 8..20, C is alone by the river.
const char* kVillage3 = R"json({
  "npcs": [
    { "id": "A", "name": "Ann", "tier": 2, "faction": "none", "initial_trust": 0, "relationship_bias": 0.1,
      "tone_weights": { "silent": 0 },
      "schedule": [ { "from_hour": 8, "to_hour": 20, "zone": "AREA-SQUARE", "activity": "loiter" },
                    { "from_hour": 20, "to_hour": 24, "zone": "AREA-HOUSES", "activity": "sleep" },
                    { "from_hour": 0, "to_hour": 8, "zone": "AREA-HOUSES", "activity": "sleep" } ] },
    { "id": "B", "name": "Bran", "tier": 2, "faction": "none", "initial_trust": 0, "relationship_bias": 0.1,
      "tone_weights": { "silent": 0 },
      "schedule": [ { "from_hour": 8, "to_hour": 20, "zone": "AREA-SQUARE", "activity": "loiter" },
                    { "from_hour": 20, "to_hour": 24, "zone": "AREA-HOUSES", "activity": "sleep" },
                    { "from_hour": 0, "to_hour": 8, "zone": "AREA-HOUSES", "activity": "sleep" } ] },
    { "id": "C", "name": "Cain", "tier": 3, "faction": "none", "initial_trust": 0, "relationship_bias": 0.1,
      "tone_weights": { "silent": 0 },
      "schedule": [ { "from_hour": 8, "to_hour": 20, "zone": "AREA-RIVERBANK", "activity": "fishing" },
                    { "from_hour": 20, "to_hour": 24, "zone": "AREA-HOUSES", "activity": "sleep" },
                    { "from_hour": 0, "to_hour": 8, "zone": "AREA-HOUSES", "activity": "sleep" } ] }
  ]
})json";

// one-rumor data: X born on day 1, seeded on A only, zone SQUARE.
// Cap defaults to 1.0 so scenario tests can chain hops freely; the dedicated
// spread-cap test passes 0.30 explicitly.
std::string MakeOneRumorData(double BaseChance, double MutationChance, double HopConfidence, int VariantCount, double Cap = 1.0)
{
        std::string Variants;
        for (int I = 0; I < VariantCount; ++I)
        {
                if (I) { Variants += ","; }
                Variants += "\"variant " + std::to_string(I) + " wording\"";
        }
        return "{\"gossip_zones\":[\"AREA-SQUARE\",\"AREA-INN\"],"
               "\"rules\":{\"base_chance\":" + std::to_string(BaseChance) +
               ",\"daily_spread_cap\":" + std::to_string(Cap) +
               ",\"mutation_chance\":" + std::to_string(MutationChance) +
               ",\"hop_confidence\":" + std::to_string(HopConfidence) + "},"
               "\"rumors\":[{"
               "\"id\":\"RUM-X\",\"topic\":\"topic-x\",\"subject\":\"HUNGER\",\"valence\":-0.5,"
               "\"origin\":\"world:test\",\"day_created\":1,\"hour_created\":8,"
               "\"place_zone\":\"AREA-SQUARE\",\"origin_confidence\":1.0,\"decay\":0.25,"
               "\"variants\":[" + Variants + "],"
               "\"seeds\":[{\"npc\":\"A\",\"kind\":\"direct\",\"confidence\":1.0}]"
               "}]}";
}

// ten co-located NPCs (N0..N9) in the square from 08 to 20 - a village big
// enough that the 30% daily cap (3) and the speaker budgets (2) do not collide.
std::string MakeTenNpcVillage()
{
        std::string TenJson = "{\"npcs\":[";
        for (int I = 0; I < 10; ++I)
        {
                if (I) { TenJson += ","; }
                TenJson += "{\"id\":\"N" + std::to_string(I) + "\",\"name\":\"n\",\"tier\":3,\"faction\":\"none\","
                           "\"initial_trust\":0,\"relationship_bias\":0.1,\"tone_weights\":{\"silent\":0},"
                           "\"schedule\":[{\"from_hour\":8,\"to_hour\":20,\"zone\":\"AREA-SQUARE\",\"activity\":\"loiter\"},"
                           "{\"from_hour\":20,\"to_hour\":24,\"zone\":\"AREA-HOUSES\",\"activity\":\"sleep\"},"
                           "{\"from_hour\":0,\"to_hour\":8,\"zone\":\"AREA-HOUSES\",\"activity\":\"sleep\"}]}";
        }
        TenJson += "]}";
        return TenJson;
}

std::unique_ptr<RumorSystem> MakeLoadedRumors(const std::string& DataJson, std::string& Err)
{
        auto Sys = MakeRumors(DataJson, Err);
        if (Sys) { Sys->ActivateDue(1); }
        return Sys;
}

// ------------------------------------------------------------ load validation

void TestLoadValidation()
{
        TLS_SECTION("Rumors - data loading and invalid-data rejection");

        std::string Err;
        {
                // minimal data with NO rules block: verifies the documented defaults
                auto Sys = MakeRumors("{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[{"
                        "\"id\":\"RUM-X\",\"origin\":\"world:test\",\"variants\":[\"a\",\"b\"],"
                        "\"seeds\":[{\"npc\":\"A\"}]}]}", Err);
                TLS_CHECK_MSG(Sys != nullptr, "valid rumor data loads: " + Err);
                if (Sys)
                {
                        TLS_CHECK(Sys->FindDef("RUM-X") != nullptr);
                        TLS_CHECK(Sys->GetRules().BaseChance == 0.60);         // default
                        TLS_CHECK(Sys->GetRules().MaxActiveRumors == 6);       // default cap
                        TLS_CHECK(Sys->GetRules().DailySpreadCap == 0.30);     // NPC_SIMULATION 10
                        TLS_CHECK(Sys->IsGossipZone("AREA-SQUARE"));
                        TLS_CHECK(!Sys->IsGossipZone("AREA-RIVERBANK"));
                }
        }
        { auto Sys = MakeRumors("{\"rumors\":[]}", Err);                       TLS_CHECK_MSG(Sys == nullptr, "no gossip zones rejected"); }
        { auto Sys = MakeRumors("{\"gossip_zones\":[\"AREA-SQUARE\"]}", Err);  TLS_CHECK_MSG(Sys == nullptr, "missing rumors array rejected"); }
        {
                auto Sys = MakeRumors("{\"gossip_zones\":[\"AREA-SQUARE\"],\"rules\":\"fast\",\"rumors\":[]}", Err);
                TLS_CHECK_MSG(Sys == nullptr, "non-object rules rejected");
        }
        {
                auto Sys = MakeRumors("{\"gossip_zones\":[\"AREA-SQUARE\"],\"npc_relationships\":5,\"rumors\":[]}", Err);
                TLS_CHECK_MSG(Sys == nullptr, "non-object relationships rejected");
        }
        {
                auto Sys = MakeRumors("{\"gossip_zones\":[\"AREA-SQUARE\"],\"npc_relationships\":{\"A\":{\"B\":-150}},\"rumors\":[]}", Err);
                TLS_CHECK_MSG(Sys == nullptr, "relationship out of range rejected");
        }
        {
                auto Sys = MakeRumors("{\"gossip_zones\":[\"AREA-SQUARE\"],\"rules\":{\"daily_spread_cap\":1.5},\"rumors\":[]}", Err);
                TLS_CHECK_MSG(Sys == nullptr, "spread cap out of range rejected");
        }
        {
                auto Sys = MakeRumors(MakeOneRumorData(0.6, 0.0, 0.8, 1) + ",\"d\":2}", Err);
                TLS_CHECK_MSG(Sys == nullptr, "malformed json rejected");
        }
        {
                // duplicate id
                std::string Data = "{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[";
                Data += "{\"id\":\"RUM-X\",\"origin\":\"w\",\"variants\":[\"a\"],\"seeds\":[]},";
                Data += "{\"id\":\"RUM-X\",\"origin\":\"w\",\"variants\":[\"a\"],\"seeds\":[]}]}";
                auto Sys = MakeRumors(Data, Err);
                TLS_CHECK_MSG(Sys == nullptr, "duplicate rumor id rejected");
        }
        {
                std::string Data = "{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[";
                Data += "{\"id\":\"RUM-X\",\"origin\":\"w\",\"valence\":1.5,\"variants\":[\"a\"],\"seeds\":[]}]}";
                auto Sys = MakeRumors(Data, Err);
                TLS_CHECK_MSG(Sys == nullptr, "valence out of range rejected");
        }
        {
                std::string Data = "{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[";
                Data += "{\"id\":\"RUM-X\",\"origin\":\"w\",\"variants\":[\"a\"],"
                        "\"seeds\":[{\"npc\":\"A\",\"variant\":3}]}]}";
                auto Sys = MakeRumors(Data, Err);
                TLS_CHECK_MSG(Sys == nullptr, "seed variant index out of range rejected");
        }
        {
                std::string Data = "{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[";
                Data += "{\"id\":\"RUM-X\",\"origin\":\"w\",\"variants\":[\"a\"],"
                        "\"seeds\":[{\"npc\":\"A\",\"kind\":\"whispered\"}]}]}";
                auto Sys = MakeRumors(Data, Err);
                TLS_CHECK_MSG(Sys == nullptr, "unknown testimony kind rejected");
        }
        {
                // seven rumors against the default cap of six (NPC_SIMULATION 11)
                std::string Data = "{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[";
                for (int I = 0; I < 7; ++I)
                {
                        if (I) { Data += ","; }
                        Data += "{\"id\":\"RUM-" + std::to_string(I) + "\",\"origin\":\"w\",\"variants\":[\"a\"],\"seeds\":[]}";
                }
                Data += "]}";
                auto Sys = MakeRumors(Data, Err);
                TLS_CHECK_MSG(Sys == nullptr, "more rumors than the active cap rejected: " + Err);
        }
}

// ------------------------------------------------------------ seeding + witness

void TestSeedingAndWitness()
{
        TLS_SECTION("Rumors - day activation and witness events");

        std::string Err;
        auto Sys = MakeLoadedRumors(MakeOneRumorData(0.6, 0.0, 0.8, 2), Err);
        TLS_CHECK(Sys != nullptr);
        if (!Sys) { return; }

        TLS_CHECK(Sys->NpcKnows("A", "RUM-X"));
        TLS_CHECK(Sys->NpcKnowledge("A", "RUM-X")->Kind == ETestimonyKind::Direct);
        TLS_CHECK(Sys->NpcKnowledge("A", "RUM-X")->HopCount == 0);
        TLS_CHECK(!Sys->NpcKnows("B", "RUM-X"));
        Sys->ActivateDue(1);                                       // idempotent re-run
        TLS_CHECK(Sys->KnowerCount("RUM-X") == 1);

        // a day-2 rumor does not exist on day 1
        auto Born = MakeRumors(
                "{\"gossip_zones\":[\"AREA-SQUARE\"],\"rumors\":[{\"id\":\"RUM-LATE\","
                "\"origin\":\"w\",\"day_created\":2,\"variants\":[\"a\"],"
                "\"seeds\":[{\"npc\":\"B\",\"kind\":\"hearsay\"}]}]}", Err);
        TLS_CHECK(Born != nullptr);
        if (Born)
        {
                Born->ActivateDue(1);
                TLS_CHECK(Born->KnowerCount("RUM-LATE") == 0);
                Born->ActivateDue(2);
                TLS_CHECK(Born->KnowerCount("RUM-LATE") == 1);
        }

        // witness events register Direct knowledge, duplicates ignored
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }
        TLS_CHECK(Sys->RegisterWitnessEvent("RUM-X", 1, 10, "AREA-INN", { "B", "C" }, Err));
        TLS_CHECK(Sys->NpcKnowledge("B", "RUM-X")->Kind == ETestimonyKind::Direct);
        TLS_CHECK(Sys->NpcKnowledge("B", "RUM-X")->HopCount == 0);
        TLS_CHECK(Sys->KnowerCount("RUM-X") == 3);
        const int TransmissionsBefore = static_cast<int>(Sys->TransmissionLog().size());
        TLS_CHECK(Sys->RegisterWitnessEvent("RUM-X", 1, 10, "AREA-INN", { "B", "C" }, Err));   // same event again
        TLS_CHECK(Sys->KnowerCount("RUM-X") == 3);
        TLS_CHECK(static_cast<int>(Sys->TransmissionLog().size()) == TransmissionsBefore);
        TLS_CHECK(!Sys->RegisterWitnessEvent("RUM-NOPE", 1, 10, "AREA-INN", { "B" }, Err));    // unknown rumor
        TLS_CHECK(!Sys->RegisterWitnessEvent("RUM-X", 1, 10, "", { "B" }, Err));               // no zone
}

// ------------------------------------------------------------ spread mechanics

void TestSpreadMechanics()
{
        TLS_SECTION("Rumors - spread bound to zones, schedules, relationships, reticence");

        std::string Err;
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }

        // base chance 1.0: the transfer must happen exactly once, and only
        // between co-located villagers inside a gossip zone
        {
                auto Sys = MakeLoadedRumors(MakeOneRumorData(1.0, 0.0, 0.8, 2), Err);
                TLS_CHECK(Sys != nullptr);
                if (!Sys) { return; }
                Rng Rng(1);
                auto Result = Sys->TickHour(1, 10, *V, Rng);
                TLS_CHECK_MSG(Result.NewTransmissions.size() == 1, "one co-located listener, one transmission");
                if (Result.NewTransmissions.size() == 1)
                {
                        const RumorTransmission& T = Result.NewTransmissions[0];
                        TLS_CHECK(T.FromNpc == "A" && T.ToNpc == "B");
                        TLS_CHECK(T.Zone == "AREA-SQUARE" && T.Day == 1 && T.Hour == 10);
                }
                TLS_CHECK(Sys->NpcKnows("B", "RUM-X"));
                TLS_CHECK(!Sys->NpcKnows("C", "RUM-X"));       // never co-located in a gossip zone
                // a second tick cannot re-tell the same listener (no duplicate recording)
                auto Result2 = Sys->TickHour(1, 11, *V, Rng);
                TLS_CHECK_MSG(Result2.NewTransmissions.empty(), "no re-telling to someone who knows");
                // outside gossip hours (both asleep in AREA-HOUSES): nothing moves
                auto Result3 = Sys->TickHour(1, 23, *V, Rng);
                TLS_CHECK(Result3.NewTransmissions.empty());
        }

        // relationship gate: estranged villagers do not gossip (NPC_SIMULATION 5)
        {
                std::string Data = MakeOneRumorData(1.0, 0.0, 0.8, 2);
                Data.insert(Data.find("\"rumors\""), "\"npc_relationships\":{\"A\":{\"B\":-15.0}},");
                auto Sys2 = MakeLoadedRumors(Data, Err);
                TLS_CHECK_MSG(Sys2 != nullptr, "relationship fixture loads: " + Err);
                if (Sys2)
                {
                        Rng Rng(1);
                        for (int Hour = 8; Hour < 20; ++Hour) { Sys2->TickHour(1, Hour, *V, Rng); }
                        TLS_CHECK_MSG(!Sys2->NpcKnows("B", "RUM-X"), "negative relationship blocks the transfer entirely");
                }
        }

        // reticence block: a mute speaker (0.9 >= 0.75) says nothing
        {
                std::string Reticent = R"json({
                  "npcs": [
                    { "id": "A", "name": "Mute", "tier": 2, "faction": "none", "initial_trust": 0,
                      "relationship_bias": 0.1, "reticence": 0.9, "tone_weights": { "silent": 0 },
                      "schedule": [ { "from_hour": 8, "to_hour": 20, "zone": "AREA-SQUARE", "activity": "loiter" },
                                    { "from_hour": 20, "to_hour": 24, "zone": "AREA-HOUSES", "activity": "sleep" },
                                    { "from_hour": 0, "to_hour": 8, "zone": "AREA-HOUSES", "activity": "sleep" } ] },
                    { "id": "B", "name": "Bran", "tier": 2, "faction": "none", "initial_trust": 0, "relationship_bias": 0.1,
                      "tone_weights": { "silent": 0 },
                      "schedule": [ { "from_hour": 8, "to_hour": 20, "zone": "AREA-SQUARE", "activity": "loiter" },
                                    { "from_hour": 20, "to_hour": 24, "zone": "AREA-HOUSES", "activity": "sleep" },
                                    { "from_hour": 0, "to_hour": 8, "zone": "AREA-HOUSES", "activity": "sleep" } ] }
                  ]
                })json";
                auto V2 = MakeVillage(Reticent, Err);
                TLS_CHECK(V2 != nullptr);
                if (V2)
                {
                        auto Sys = MakeLoadedRumors(MakeOneRumorData(1.0, 0.0, 0.8, 2), Err);
                        TLS_CHECK(Sys != nullptr);
                        if (Sys)
                        {
                                Rng Rng(1);
                                for (int Hour = 8; Hour < 20; ++Hour) { Sys->TickHour(1, Hour, *V2, Rng); }
                                TLS_CHECK_MSG(!Sys->NpcKnows("B", "RUM-X"), "reticent speaker (0.9 >= block 0.75) never spreads");
                        }
                }
        }

        // trust rule: hostile talk about EDMUND slows down through trusted mouths.
        // base chance 1.0 always transmits (chance gate short-circuits at 1.0);
        // trust 100 halves it to 0.5, so high-trust tellings <= low-trust tellings
        // across 40 deterministic runs.
        {
                const std::string Edmund = MakeOneRumorData(1.0, 0.0, 0.8, 2);
                long TotalLowTrust = 0, TotalHighTrust = 0;
                for (int Seed = 1; Seed <= 40; ++Seed)
                {
                        auto V3 = MakeVillage(kVillage3, Err);
                        auto Low = MakeLoadedRumors(Edmund, Err);
                        if (!V3 || !Low) { TLS_CHECK_MSG(false, "trust fixture failed"); return; }
                        Rng R1(Seed);
                        Low->TickHour(1, 10, *V3, R1);
                        // high-trust run: the SPEAKER (first NPC) starts at trust 100
                        std::string Trusted = std::string(kVillage3);
                        Trusted.replace(Trusted.find("\"initial_trust\": 0"), 18, "\"initial_trust\": 100");
                        auto V4 = MakeVillage(Trusted, Err);
                        auto High = MakeLoadedRumors(Edmund, Err);
                        if (!V4 || !High) { TLS_CHECK_MSG(false, "trusted village fixture failed"); return; }
                        Rng R2(Seed);
                        High->TickHour(1, 10, *V4, R2);
                        // a telling happened iff the listener ended up knowing (seed A + listener B = 2)
                        TotalLowTrust += (Low->KnowerCount("RUM-X") >= 2) ? 1 : 0;
                        TotalHighTrust += (High->KnowerCount("RUM-X") >= 2) ? 1 : 0;
                }
                TLS_CHECK_MSG(TotalHighTrust <= TotalLowTrust,
                        "trust dampens spread (low-trust tellings >= high-trust tellings)");
                TLS_CHECK_MSG(TotalLowTrust == 40, "chance 1.0 always transmits (got " + std::to_string(TotalLowTrust) + ")");
        }
}

// ------------------------------------------------------------ spread termination

void TestSpreadTermination()
{
        TLS_SECTION("Rumors - termination: daily cap, budgets, saturation, forgetting");

        std::string Err;
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }

        // speaker budgets: hourly 1, daily 2. Isolation trick: N0 is the only
        // NPC on speaking terms with everyone - N1..N9 are mutually estranged,
        // so the rumor cannot chain hands and only N0 ever tells.
        {
                std::string Budget = "{\"gossip_zones\":[\"AREA-SQUARE\"],"
                        "\"rules\":{\"base_chance\":1.0,\"daily_spread_cap\":1.0,\"mutation_chance\":0.0,\"hop_confidence\":0.8,"
                        "\"speaker_hourly_budget\":1,\"speaker_daily_budget\":2},"
                        "\"npc_relationships\":{";
                // N0 likes everybody; N1..N9 shun each other (directed pairs)
                Budget += "\"N0\":{";
                for (int I = 1; I < 10; ++I) { if (I > 1) { Budget += ","; } Budget += "\"N" + std::to_string(I) + "\":20.0"; }
                Budget += "}";
                for (int I = 1; I < 10; ++I)
                {
                        Budget += ",\"N" + std::to_string(I) + "\":{";
                        bool First = true;
                        for (int J = 0; J < 10; ++J)
                        {
                                if (I == J) { continue; }
                                if (!First) { Budget += ","; }
                                Budget += "\"N" + std::to_string(J) + "\":" + (J == 0 ? "20.0" : "-10.0");
                                First = false;
                        }
                        Budget += "}";
                }
                Budget += "},\"rumors\":["
                        "{\"id\":\"RUM-X\",\"topic\":\"t1\",\"subject\":\"HUNGER\",\"valence\":-0.5,\"origin\":\"w\","
                        "\"day_created\":1,\"hour_created\":8,\"place_zone\":\"AREA-SQUARE\",\"origin_confidence\":1.0,"
                        "\"decay\":0.25,\"variants\":[\"a\",\"b\"],\"seeds\":[{\"npc\":\"N0\",\"kind\":\"direct\"}]}]}";
                auto V10 = MakeVillage(MakeTenNpcVillage(), Err);
                TLS_CHECK(V10 != nullptr);
                auto Sys = MakeLoadedRumors(Budget, Err);
                TLS_CHECK(Sys != nullptr);
                if (!Sys || !V10)
                {
                        TLS_CHECK_MSG(false, "budget fixture failed: " + Err);
                        return;
                }
                Rng Rng(1);
                int Total = 0, N0Told = 0;
                for (int Hour = 8; Hour < 20; ++Hour)
                {
                        auto R = Sys->TickHour(1, Hour, *V10, Rng);
                        for (const RumorTransmission& T : R.NewTransmissions)
                        {
                                ++Total;
                                if (T.FromNpc == "N0") { ++N0Told; }
                        }
                }
                // hourly budget 1 spreads the tellings across hours; daily budget 2 stops N0 after two
                TLS_CHECK_MSG(Total == 2, "only the speaker's two daily tellings happen (got " + std::to_string(Total) + ")");
                TLS_CHECK_MSG(N0Told == 2, "both tellings came from N0");
                TLS_CHECK(Sys->NpcKnows("N1", "RUM-X") && Sys->NpcKnows("N2", "RUM-X"));
                TLS_CHECK(!Sys->NpcKnows("N3", "RUM-X"));   // budget spent before reaching N3
        }

        // saturation: when everyone knows, gossip produces nothing (no infinite re-gossip)
        {
                auto Sys = MakeLoadedRumors(MakeOneRumorData(1.0, 0.0, 0.8, 2), Err);
                TLS_CHECK(Sys != nullptr);
                if (!Sys) { return; }
                Rng Rng(1);
                Sys->TickHour(1, 8, *V, Rng);     // A -> B
                auto Satiated = Sys->TickHour(1, 9, *V, Rng);
                TLS_CHECK(Satiated.NewTransmissions.empty());   // A,B know; C out of zone
                // decay the rumor out of memory entirely: 0.75^n drops below the
                // forget threshold 0.15 on the 7th day (1.0 -> ... -> 0.133)
                for (int Day = 1; Day <= 8; ++Day) { Sys->ApplyDailyDecay(Day); }
                TLS_CHECK_MSG(Sys->KnowerCount("RUM-X") == 0, "forget threshold erases faded knowledge");
                TLS_CHECK(Sys->ActiveRumorIds().empty());
        }

        // the daily spread cap is a DAY budget, not per hour: 10 co-located NPCs, cap 30%
        {
                auto V10 = MakeVillage(MakeTenNpcVillage(), Err);
                TLS_CHECK(V10 != nullptr);
                if (V10)
                {
                        std::string Data = MakeOneRumorData(1.0, 0.0, 0.8, 2, 0.30);
                        auto Sys = MakeRumors(Data, Err);
                        TLS_CHECK(Sys != nullptr);
                        if (Sys)
                        {
                                Sys->RegisterWitnessEvent("RUM-X", 1, 8, "AREA-SQUARE", { "N0" }, Err);
                                Rng Rng(1);
                                int NewToday = 0;
                                for (int Hour = 8; Hour < 20; ++Hour)
                                {
                                        auto R = Sys->TickHour(1, Hour, *V10, Rng);
                                        NewToday += static_cast<int>(R.NewTransmissions.size());
                                }
                                // floor(0.30 * 10) = 3 new knowers max for the whole day
                                TLS_CHECK_MSG(NewToday == 3, "daily spread cap: 30% of 10 villagers = 3 (got " + std::to_string(NewToday) + ")");
                                TLS_CHECK(Sys->KnowerCount("RUM-X") == 4);   // seed + 3
                        }
                }
        }
}

// ------------------------------------------------------------ credibility + testimony kinds

void TestCredibilityAndKinds()
{
        TLS_SECTION("Rumors - credibility decay and testimony kinds");

        std::string Err;
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }

        // hop confidence: 1.0 -> 0.5 -> 0.25 (hop_confidence 0.5, no mutation)
        {
                auto Sys = MakeLoadedRumors(MakeOneRumorData(1.0, 0.0, 0.5, 2), Err);
                TLS_CHECK(Sys != nullptr);
                if (!Sys) { return; }
                Rng Rng(1);
                Sys->TickHour(1, 8, *V, Rng);     // A -> B
                // hour 2: A stays home (first AREA-SQUARE in the fixture is A's day
                // zone) and C joins the square, so the second tell must come from B
                std::string SecondHour = std::string(kVillage3);
                SecondHour.replace(SecondHour.find("\"AREA-SQUARE\""), 13, "\"AREA-HOUSES\"");
                SecondHour.replace(SecondHour.find("\"AREA-RIVERBANK\""), 16, "\"AREA-SQUARE\"");
                auto V2 = MakeVillage(SecondHour, Err);
                TLS_CHECK(V2 != nullptr);
                if (V2)
                {
                        Sys->TickHour(1, 9, *V2, Rng);        // B -> C
                        const RumorKnowledge* KB = Sys->NpcKnowledge("B", "RUM-X");
                        const RumorKnowledge* KC = Sys->NpcKnowledge("C", "RUM-X");
                        TLS_CHECK(KB && KC);
                        if (KB && KC)
                        {
                                TLS_CHECK_MSG(std::fabs(KB->Confidence - 0.5) < 1e-9, "hop 1 confidence = 0.5");
                                TLS_CHECK_MSG(std::fabs(KC->Confidence - 0.25) < 1e-9, "hop 2 confidence = 0.25");
                                TLS_CHECK(KB->HopCount == 1 && KC->HopCount == 2);
                                TLS_CHECK(KB->FromNpc == "A" && KC->FromNpc == "B");
                                // kind degradation: hearsay below 0.40 reports Unverified
                                TLS_CHECK(Sys->NpcEffectiveKind("B", "RUM-X") == ETestimonyKind::Hearsay);
                                TLS_CHECK(Sys->NpcEffectiveKind("C", "RUM-X") == ETestimonyKind::Unverified);
                        }
                        // daily decay: B's 0.5 * (1 - 0.25) = 0.375
                        Sys->ApplyDailyDecay(2);
                        if (KB) { TLS_CHECK_MSG(std::fabs(KB->Confidence - 0.375) < 1e-9, "daily decay applied once"); }
                        // direct witnesses never degrade in kind
                        TLS_CHECK(Sys->NpcEffectiveKind("A", "RUM-X") == ETestimonyKind::Direct);
                        // someone who knows nothing reports the weakest claim
                        TLS_CHECK(Sys->NpcEffectiveKind("Z", "RUM-X") == ETestimonyKind::Unverified);
                }
        }

        // heavy mutation alone marks the claim unverified (confidence stays full)
        {
                auto Sys = MakeLoadedRumors(MakeOneRumorData(1.0, 1.0, 1.0, 3), Err);
                TLS_CHECK(Sys != nullptr);
                if (!Sys) { return; }
                Rng Rng(1);
                Sys->TickHour(1, 8, *V, Rng);
                std::string SecondHour = std::string(kVillage3);
                SecondHour.replace(SecondHour.find("\"AREA-SQUARE\""), 13, "\"AREA-HOUSES\"");
                SecondHour.replace(SecondHour.find("\"AREA-RIVERBANK\""), 16, "\"AREA-SQUARE\"");
                auto V2 = MakeVillage(SecondHour, Err);
                TLS_CHECK(V2 != nullptr);
                if (V2)
                {
                        Sys->TickHour(1, 9, *V2, Rng);
                        const RumorKnowledge* KC = Sys->NpcKnowledge("C", "RUM-X");
                        TLS_CHECK(KC && KC->VariantIndex == 2);
                        if (KC)
                        {
                                TLS_CHECK_MSG(std::fabs(KC->Confidence - 1.0) < 1e-9, "hop_confidence 1.0 keeps confidence full");
                                TLS_CHECK_MSG(Sys->NpcEffectiveKind("C", "RUM-X") == ETestimonyKind::Unverified,
                                        "two mutations mark the wording unverified even at full confidence");
                        }
                }
        }
}

// ------------------------------------------------------------ conflicts + provenance

void TestConflictsAndProvenance()
{
        TLS_SECTION("Rumors - testimony conflicts and source tracking");

        std::string Err;
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }

        // two rumors on one topic with opposite valence = a conflict for whoever holds both
        std::string Data = "{\"gossip_zones\":[\"AREA-SQUARE\"],"
                "\"rules\":{\"base_chance\":1.0,\"mutation_chance\":0.0,\"hop_confidence\":0.8},"
                "\"rumors\":["
                "{\"id\":\"RUM-BAD\",\"topic\":\"shoni\",\"subject\":\"SHONI\",\"valence\":-0.8,\"origin\":\"w\","
                "\"day_created\":1,\"hour_created\":8,\"place_zone\":\"AREA-SQUARE\",\"origin_confidence\":1.0,"
                "\"decay\":0.1,\"variants\":[\"bad\"],\"seeds\":[{\"npc\":\"A\",\"kind\":\"direct\"}]},"
                "{\"id\":\"RUM-GOOD\",\"topic\":\"shoni\",\"subject\":\"SHONI\",\"valence\":0.6,\"origin\":\"w2\","
                "\"day_created\":1,\"hour_created\":8,\"place_zone\":\"AREA-SQUARE\",\"origin_confidence\":1.0,"
                "\"decay\":0.1,\"variants\":[\"good\"],\"seeds\":[{\"npc\":\"A\",\"kind\":\"direct\"}]},"
                "{\"id\":\"RUM-OTHER\",\"topic\":\"weather\",\"subject\":\"HUNGER\",\"valence\":-0.5,\"origin\":\"w3\","
                "\"day_created\":1,\"hour_created\":8,\"place_zone\":\"AREA-SQUARE\",\"origin_confidence\":1.0,"
                "\"decay\":0.1,\"variants\":[\"o\"],\"seeds\":[{\"npc\":\"A\",\"kind\":\"direct\"}]}]}";
        auto Sys = MakeLoadedRumors(Data, Err);
        TLS_CHECK(Sys != nullptr);
        if (!Sys) { return; }

        // A knows all three: one conflict pair (BAD vs GOOD on topic shoni)
        auto ConfA = Sys->FindConflicts("A");
        TLS_CHECK_MSG(ConfA.size() == 1, "one opposite-valence pair on the same topic (got " + std::to_string(ConfA.size()) + ")");
        if (ConfA.size() == 1)
        {
                TLS_CHECK(ConfA[0].Topic == "shoni");
                TLS_CHECK((ConfA[0].RumorA == "RUM-BAD" && ConfA[0].RumorB == "RUM-GOOD")
                       || (ConfA[0].RumorA == "RUM-GOOD" && ConfA[0].RumorB == "RUM-BAD"));
        }
        TLS_CHECK(Sys->FindConflicts("C").empty());       // knows nothing
        // unknown NPC: no knowledge, no conflicts
        TLS_CHECK(Sys->FindConflicts("ZZ").empty());

        // spread to B, then check provenance chains against the transmission log
        Rng Rng(1);
        Sys->TickHour(1, 8, *V, Rng);   // A -> B (one rumor)
        Sys->TickHour(1, 9, *V, Rng);   // A -> B (second rumor; hourly budget 1 per speaker)

        auto Chain = Sys->TraceProvenance("RUM-BAD", "B");
        TLS_CHECK_MSG(Chain.size() == 1, "one-hop chain for a direct tell");
        if (Chain.size() == 1)
        {
                TLS_CHECK(Chain[0].FromNpc == "A" && Chain[0].ToNpc == "B" && Chain[0].Day == 1);
        }
        // every provenance step must exist in the append-only transmission log
        bool AllStepsReal = true;
        for (const auto& KV : Sys->Defs())
        {
                for (const std::string& Holder : Sys->NpcsKnowing(KV.first))
                {
                        for (const RumorTransmission& Step : Sys->TraceProvenance(KV.first, Holder))
                        {
                                bool Found = false;
                                for (const RumorTransmission& T : Sys->TransmissionLog())
                                {
                                        if (T.RumorId == Step.RumorId && T.FromNpc == Step.FromNpc && T.ToNpc == Step.ToNpc
                                                && T.Day == Step.Day && T.Hour == Step.Hour) { Found = true; break; }
                                }
                                if (!Found) { AllStepsReal = false; }
                        }
                }
        }
        TLS_CHECK_MSG(AllStepsReal, "every provenance step is a recorded transmission");
        TLS_CHECK(Sys->TraceProvenance("RUM-BAD", "A").empty());    // origin: no incoming chain
        TLS_CHECK(Sys->TraceProvenance("RUM-BAD", "QQ").empty());   // unknown holder
}

// ------------------------------------------------------------ mutation

void TestMutation()
{
        TLS_SECTION("Rumors - content mutation hop by hop");

        std::string Err;
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }

        // mutation_chance 1.0: every hop drifts one variant forward
        {
                auto Sys = MakeLoadedRumors(MakeOneRumorData(1.0, 1.0, 0.8, 3), Err);
                TLS_CHECK(Sys != nullptr);
                if (!Sys) { return; }
                Rng Rng(1);
                Sys->TickHour(1, 8, *V, Rng);
                const RumorKnowledge* KB = Sys->NpcKnowledge("B", "RUM-X");
                TLS_CHECK(KB && KB->VariantIndex == 1);
                std::string SecondHour = std::string(kVillage3);
                SecondHour.replace(SecondHour.find("\"AREA-SQUARE\""), 13, "\"AREA-HOUSES\"");
                SecondHour.replace(SecondHour.find("\"AREA-RIVERBANK\""), 16, "\"AREA-SQUARE\"");
                auto V2 = MakeVillage(SecondHour, Err);
                if (V2 && KB)
                {
                        Sys->TickHour(1, 9, *V2, Rng);
                        const RumorKnowledge* KC = Sys->NpcKnowledge("C", "RUM-X");
                        TLS_CHECK(KC && KC->VariantIndex == 2);
                        // the transmission log records the mutated wording index
                        if (KC && KC->VariantIndex == 2)
                        {
                                const RumorTransmission& Last = Sys->TransmissionLog().back();
                                TLS_CHECK(Last.ToNpc == "C" && Last.VariantIndex == 2);
                        }
                }
        }
        // the mutation never runs past the last variant
        {
                auto Sys = MakeLoadedRumors(MakeOneRumorData(1.0, 1.0, 0.8, 2), Err);
                TLS_CHECK(Sys != nullptr);
                if (!Sys) { return; }
                Rng Rng(1);
                Sys->TickHour(1, 8, *V, Rng);
                std::string SecondHour = std::string(kVillage3);
                SecondHour.replace(SecondHour.find("\"AREA-SQUARE\""), 13, "\"AREA-HOUSES\"");
                SecondHour.replace(SecondHour.find("\"AREA-RIVERBANK\""), 16, "\"AREA-SQUARE\"");
                auto V2 = MakeVillage(SecondHour, Err);
                if (V2)
                {
                        Sys->TickHour(1, 9, *V2, Rng);
                        const RumorKnowledge* KC = Sys->NpcKnowledge("C", "RUM-X");
                        TLS_CHECK(KC && KC->VariantIndex == 1);   // clamped at variants.size()-1
                }
        }
        // determinism: same seed -> identical state; different seed -> different story
        {
                auto S1 = MakeLoadedRumors(MakeOneRumorData(0.6, 0.25, 0.8, 3), Err);
                auto S2 = MakeLoadedRumors(MakeOneRumorData(0.6, 0.25, 0.8, 3), Err);
                auto S3 = MakeLoadedRumors(MakeOneRumorData(0.6, 0.25, 0.8, 3), Err);
                TLS_CHECK(S1 && S2 && S3);
                if (S1 && S2 && S3)
                {
                        Rng R1(11), R2(11), R3(99);
                        for (int Hour = 8; Hour < 14; ++Hour)
                        {
                                S1->TickHour(1, Hour, *V, R1);
                                S2->TickHour(1, Hour, *V, R2);
                                S3->TickHour(1, Hour, *V, R3);
                        }
                        TLS_CHECK_MSG(JsonSerialize(S1->SerializeState(), false) == JsonSerialize(S2->SerializeState(), false),
                                "same seed reproduces the same gossip hour by hour");
                        TLS_CHECK_MSG(JsonSerialize(S1->SerializeState(), false) != JsonSerialize(S3->SerializeState(), false),
                                "a different seed tells a different story");
                }
        }
}

// ------------------------------------------------------------ player tools

void TestPlayerTools()
{
        TLS_SECTION("Rumors - player tools: heard, leak, public denial");

        std::string Err;
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }

        auto Sys = MakeLoadedRumors(MakeOneRumorData(0.6, 0.0, 0.8, 2), Err);
        TLS_CHECK(Sys != nullptr);
        if (!Sys) { return; }

        // heard: no duplicates, unknown ids refused
        TLS_CHECK(Sys->NotifyPlayerHeard("RUM-X", 1, 10, "B"));
        TLS_CHECK(!Sys->NotifyPlayerHeard("RUM-NOPE", 1, 10, "B"));
        TLS_CHECK(Sys->NotifyPlayerHeard("RUM-X", 1, 10, "B"));    // second hearing is a no-op
        TLS_CHECK(Sys->PlayerKnownRumors().size() == 1);
        TLS_CHECK(Sys->PlayerKnownRumors()[0] == "RUM-X");

        // leak: everyone present in the gossip zone hears the anonymous word
        {
                auto Fresh = MakeLoadedRumors(MakeOneRumorData(0.6, 0.0, 0.8, 2), Err);
                TLS_CHECK(Fresh != nullptr);
                if (!Fresh) { return; }
                const int Heard = Fresh->NotifyPlayerLeak("RUM-X", 1, 10, "AREA-SQUARE", *V, Err);
                TLS_CHECK_MSG(Heard == 1, "leak reaches zone occupants only (A knows, B listens) - got " + std::to_string(Heard));
                TLS_CHECK(Fresh->NpcKnows("B", "RUM-X"));
                if (const RumorKnowledge* KB = Fresh->NpcKnowledge("B", "RUM-X"))
                {
                        TLS_CHECK(KB->FromNpc == "PLAYER");
                        TLS_CHECK(KB->Kind == ETestimonyKind::Hearsay);   // anonymous word is never direct
                        TLS_CHECK(std::fabs(KB->Confidence - 0.55) < 1e-9);
                        TLS_CHECK(KB->HopCount == 1);
                }
                // provenance runs through the PLAYER transmission
                auto Chain = Fresh->TraceProvenance("RUM-X", "B");
                TLS_CHECK(Chain.size() == 1 && Chain[0].FromNpc == "PLAYER" && Chain[0].ToNpc == "B");
                // second leak the same hour records nothing new
                TLS_CHECK(Fresh->NotifyPlayerLeak("RUM-X", 1, 10, "AREA-SQUARE", *V, Err) == 0);
                // invalid leaks are refused
                TLS_CHECK(Fresh->NotifyPlayerLeak("RUM-X", 1, 10, "AREA-RIVERBANK", *V, Err) == -1);
                TLS_CHECK(Fresh->NotifyPlayerLeak("RUM-NOPE", 1, 10, "AREA-SQUARE", *V, Err) == -1);
        }

        // denial: every holder loses 0.30 confidence and the day's gossip is dulled
        {
                auto Fresh = MakeLoadedRumors(MakeOneRumorData(0.6, 0.0, 0.8, 2), Err);
                TLS_CHECK(Fresh != nullptr);
                if (!Fresh) { return; }
                // one extra holder with known confidence
                Fresh->RegisterWitnessEvent("RUM-X", 1, 9, "AREA-INN", { "B" }, Err);
                const double Before = Fresh->NpcKnowledge("B", "RUM-X")->Confidence;   // 1.0 (origin confidence)
                const int Affected = Fresh->NotifyPlayerDenial(1, 10);
                TLS_CHECK(Affected == Fresh->KnowerCount("RUM-X"));
                TLS_CHECK_MSG(std::fabs(Fresh->NpcKnowledge("B", "RUM-X")->Confidence - (Before - 0.30)) < 1e-9,
                        "denial subtracts 0.30 from holder confidence");
                // dulled gossip: aggregate 40 deterministic runs, same seed pairs
                long ToldNormal = 0, ToldDulled = 0;
                for (int Seed = 1; Seed <= 40; ++Seed)
                {
                        auto Quiet = MakeLoadedRumors(MakeOneRumorData(0.6, 0.0, 0.8, 2), Err);
                        auto Loud = MakeLoadedRumors(MakeOneRumorData(0.6, 0.0, 0.8, 2), Err);
                        if (!Quiet || !Loud) { TLS_CHECK_MSG(false, "denial fixture failed"); return; }
                        Quiet->NotifyPlayerDenial(1, 8);
                        Rng R1(Seed), R2(Seed);
                        Quiet->TickHour(1, 10, *V, R1);
                        Loud->TickHour(1, 10, *V, R2);
                        ToldDulled += Quiet->KnowerCount("RUM-X");
                        ToldNormal += Loud->KnowerCount("RUM-X");
                }
                TLS_CHECK_MSG(ToldDulled < ToldNormal, "a public denial halves the day's telling chance");
                // the dulling state must survive serialization
                Fresh->NotifyPlayerDenial(3, 8);
                JsonValue Saved = Fresh->SerializeState();
                auto Restored = std::make_unique<RumorSystem>();
                // defs must exist for a state load - reload data first
                JsonParseResult DataP = JsonParse(MakeOneRumorData(0.6, 0.0, 0.8, 2));
                TLS_CHECK(Restored->Load(DataP.Value, Err));
                TLS_CHECK(Restored->DeserializeState(Saved, Err));
                TLS_CHECK(Restored->NpcKnows("B", "RUM-X"));
        }
}

// ------------------------------------------------------------ rumor save/load

void TestRumorSaveLoad()
{
        TLS_SECTION("Rumors - state serialization and corrupt-payload rejection");

        std::string Err;
        auto V = MakeVillage(kVillage3, Err);
        TLS_CHECK(V != nullptr);
        if (!V) { return; }

        std::string Data = MakeOneRumorData(1.0, 0.25, 0.8, 3);
        auto Source = MakeLoadedRumors(Data, Err);
        TLS_CHECK(Source != nullptr);
        if (!Source) { return; }
        Rng Rng(1);
        Source->TickHour(1, 8, *V, Rng);
        Source->RegisterWitnessEvent("RUM-X", 1, 12, "AREA-INN", { "C" }, Err);
        Source->NotifyPlayerHeard("RUM-X", 1, 13, "B");
        Source->NotifyPlayerDenial(1, 14);

        const std::string SavedText = JsonSerialize(Source->SerializeState(), false);
        JsonParseResult Reparsed = JsonParse(SavedText);
        TLS_CHECK_MSG(Reparsed.Ok, "rumor state serializes to valid JSON");

        // restore into a fresh system with the same defs
        auto Target = MakeRumors(Data, Err);
        TLS_CHECK(Target != nullptr);
        if (!Target) { return; }
        TLS_CHECK(Target->DeserializeState(Reparsed.Value, Err));
        TLS_CHECK_MSG(JsonSerialize(Target->SerializeState(), false) == SavedText,
                "round-trip restore is byte-identical");
        TLS_CHECK(Target->NpcKnows("B", "RUM-X") && Target->NpcKnows("C", "RUM-X"));
        TLS_CHECK(Target->PlayerKnownRumors().size() == 1);
        TLS_CHECK(Target->TraceProvenance("RUM-X", "B").size() == Source->TraceProvenance("RUM-X", "B").size());

        // corrupt payloads are rejected and leave no partial state
        const char* Corrupt[] = {
                "{\"knowledge\":{\"B\":[{\"rumor\":\"RUM-X\",\"confidence\":1.5}]}}",          // confidence out of range
                "{\"knowledge\":{\"B\":[{\"rumor\":\"RUM-GHOST\"}]}}",                        // unknown rumor
                "{\"knowledge\":{\"B\":[{\"rumor\":\"RUM-X\",\"variant\":9}]}}",              // variant out of range
                "{\"knowledge\":{\"B\":[{\"rumor\":\"RUM-X\",\"kind\":\"gossip\"}]}}",        // bad kind
                "{\"knowledge\":{\"B\":[{\"rumor\":\"RUM-X\",\"day\":20}]}}",                 // day out of range
                "{\"transmissions\":[{\"rumor\":\"RUM-X\",\"day\":0,\"hour\":5}]}",           // transmission day
                "{\"last_denial_day\":15}",                                                    // denial day out of range
                "{\"knowledge\":5}",                                                           // wrong type
                "{\"transmissions\":3}"                                                        // wrong type
        };
        for (const char* Bad : Corrupt)
        {
                auto Fresh = MakeRumors(Data, Err);
                TLS_CHECK(Fresh != nullptr);
                if (!Fresh) { return; }
                JsonParseResult PB = JsonParse(Bad);
                TLS_CHECK_MSG(PB.Ok, "corrupt fixture is valid json");
                std::string BadErr;
                TLS_CHECK_MSG(!Fresh->DeserializeState(PB.Value, BadErr), std::string("rejected: ") + Bad);
                TLS_CHECK_MSG(Fresh->NpcsKnowing("RUM-X").empty(), "rejected load leaves no partial state");
        }
}

} // anonymous namespace

namespace tls_test_rumors
{

void RunAll()
{
        TestLoadValidation();
        TestSeedingAndWitness();
        TestSpreadMechanics();
        TestSpreadTermination();
        TestCredibilityAndKinds();
        TestConflictsAndProvenance();
        TestMutation();
        TestPlayerTools();
        TestRumorSaveLoad();
}

} // namespace tls_test_rumors
