// THE LAST SIN: The Sin-Eater - M2.4
// test_settings: settings & accessibility tests.
// Every setting here must drive a real system behavior in the core; UE-side
// presentation bindings are engine work and are NOT covered (nor claimed).

#include "tls_test_framework.h"
#include "test_fixtures.h"
#include "TLSJson.h"
#include "TLSSettings.h"
#include "TLSGameState.h"

#include <cmath>
#include <string>

using namespace tls;

namespace tls_test_settings
{
void RunAll(Game& G);
}

namespace
{

void TestVolumesAndClamping()
{
        TLS_SECTION("M2.4 settings - audio values clamp, subtitle policy is real");

        SettingsModel S;
        TLS_CHECK(S.MasterVolume() == 1.0 && S.DialogueVolume() == 1.0);

        S.SetMasterVolume(-0.5);
        S.SetMusicVolume(1.7);
        S.SetSfxVolume(0.42);
        TLS_CHECK(S.MasterVolume() == 0.0);
        TLS_CHECK(S.MusicVolume() == 1.0);
        TLS_CHECK(std::fabs(S.SfxVolume() - 0.42) < 1e-9);

        // the subtitle policy: a quiet dialogue channel forces subtitles on
        TLS_CHECK(!S.SubtitlesForced());
        S.SetDialogueVolume(0.10);
        TLS_CHECK_MSG(S.SubtitlesForced(), "dialogue volume 0.10 < 0.20 forces subtitles");
        S.SetDialogueVolume(0.9);
        S.SetSubtitlesAlways(true);
        TLS_CHECK_MSG(S.SubtitlesForced(), "subtitles_always forces them regardless of volume");
        S.SetSubtitlesAlways(false);
        TLS_CHECK(!S.SubtitlesForced());
}

void TestQualityTierBudget()
{
        TLS_SECTION("M2.4 settings - quality tier maps to the real gossip-tick budget");

        SettingsModel S;
        S.SetQualityTier(EQualityTier::Low);
        TLS_CHECK(S.GossipTicksPerFrame() == 1);
        S.SetQualityTier(EQualityTier::Medium);
        TLS_CHECK(S.GossipTicksPerFrame() == 2);
        S.SetQualityTier(EQualityTier::High);
        TLS_CHECK(S.GossipTicksPerFrame() == 4);

        // REAL consumer demonstration: a frame loop that drains the day's gossip
        // hours through the per-frame budget needs different frame counts per tier
        auto FramesForDay = [&S]()
        {
                const int Budget = S.GossipTicksPerFrame();
                int RemainingHours = 14;   // hours 8..21
                int Frames = 0;
                while (RemainingHours > 0)
                {
                        const int Spent = Budget < RemainingHours ? Budget : RemainingHours;
                        RemainingHours -= Spent;
                        ++Frames;
                }
                return Frames;
        };
        S.SetQualityTier(EQualityTier::Low);
        TLS_CHECK(FramesForDay() == 14);
        S.SetQualityTier(EQualityTier::High);
        TLS_CHECK(FramesForDay() == 4);
}

void TestColorblindPalettes()
{
        TLS_SECTION("M2.4 settings - colorblind palettes are real token tables");

        SettingsModel S;
        const BoardPalette None = S.BoardColors();
        TLS_CHECK(None.Link == "#E8A34D" && None.Contradiction == "#7FA8C9");   // GAME_BIBLE 7.2
        TLS_CHECK(None.Background == "#D9CBB2" && None.Ink == "#1C2226");

        S.SetColorblindMode(EColorblindMode::Deuteranopia);
        const BoardPalette Deut = S.BoardColors();
        TLS_CHECK_MSG(Deut.Contradiction != None.Contradiction, "deuteranopia moves the confusion-axis color");
        TLS_CHECK(Deut.Background == None.Background && Deut.Ink == None.Ink);

        S.SetColorblindMode(EColorblindMode::Protanopia);
        TLS_CHECK(S.BoardColors().Contradiction != None.Contradiction);
        TLS_CHECK(S.BoardColors().Contradiction != Deut.Contradiction);

        S.SetColorblindMode(EColorblindMode::Tritanopia);
        const BoardPalette Trit = S.BoardColors();
        TLS_CHECK_MSG(Trit.Link != None.Link, "tritanopia leaves the blue-yellow axis entirely");
        TLS_CHECK(Trit.Link != Deut.Link && Trit.Contradiction != Deut.Contradiction);

        // every mode keeps the four tokens distinct - no invisible lines
        for (int M = 0; M < 4; ++M)
        {
                S.SetColorblindMode(static_cast<EColorblindMode>(M));
                const BoardPalette& P = S.BoardColors();
                TLS_CHECK(P.Link != P.Contradiction);
                TLS_CHECK(P.Link != P.Background && P.Contradiction != P.Background);
        }
}

void TestTextScale()
{
        TLS_SECTION("M2.4 settings - large text doubles as the dialogue readability scale");

        SettingsModel S;
        TLS_CHECK(std::fabs(S.TextScale() - 1.0) < 1e-9);
        S.SetLargeText(true);
        TLS_CHECK(std::fabs(S.TextScale() - 1.5) < 1e-9);
        TLS_CHECK(S.UsesLargeText());
        S.SetLargeText(false);
        TLS_CHECK(std::fabs(S.TextScale() - 1.0) < 1e-9);
}

void TestInputBindings()
{
        TLS_SECTION("M2.4 settings - input bindings validate, conflicts are rejected");

        SettingsModel S;
        TLS_CHECK(S.Binding("Interact") == "E");
        TLS_CHECK(S.Binding("Pad_Interact") == "Gamepad_FaceButton_Bottom");
        TLS_CHECK(S.Bindings().size() >= 14);   // keyboard + gamepad defaults

        // rebinding a free code works
        TLS_CHECK(S.SetBinding("Journal", "K"));
        TLS_CHECK(S.Binding("Journal") == "K");

        // stealing another action's code is refused - never silently remapped
        TLS_CHECK_MSG(!S.SetBinding("RumorLeak", "K"), "K is taken by Journal - refused");
        TLS_CHECK(S.Binding("RumorLeak") == "Q");

        // a gamepad code is just as protected
        TLS_CHECK_MSG(!S.SetBinding("Pause", "Gamepad_FaceButton_Bottom"), "gamepad conflicts refused too");
        // rebinding onto itself is a no-op success
        TLS_CHECK(S.SetBinding("Interact", "E"));
        TLS_CHECK_MSG(!S.SetBinding("Interact", ""), "empty codes refused");
}

void TestSettingsPersistence(Game& G)
{
        TLS_SECTION("M2.4 settings - persistence round trip and corrupt rejection");

        SettingsModel S;
        S.SetMasterVolume(0.7);
        S.SetDialogueVolume(0.15);
        S.SetQualityTier(EQualityTier::Low);
        S.SetLargeText(true);
        S.SetColorblindMode(EColorblindMode::Deuteranopia);
        S.SetSubtitlesAlways(true);
        S.SetRumorJournalAuto(false);
        TLS_CHECK(S.SetBinding("Journal", "K"));

        const std::string Saved = JsonSerialize(S.SerializeState(), false);
        JsonParseResult P = JsonParse(Saved);
        TLS_CHECK_MSG(P.Ok, "settings serialize to valid JSON");

        SettingsModel R;   // fresh defaults
        std::string Err;
        TLS_CHECK_MSG(R.DeserializeState(P.Value, Err), "settings round trip: " + Err);
        TLS_CHECK(R.MasterVolume() == 0.7);
        TLS_CHECK(R.DialogueVolume() == 0.15);
        TLS_CHECK_MSG(R.SubtitlesForced(), "restored quiet dialogue still forces subtitles");
        TLS_CHECK(R.GetQualityTier() == EQualityTier::Low && R.GossipTicksPerFrame() == 1);
        TLS_CHECK(R.UsesLargeText());
        TLS_CHECK(R.GetColorblindMode() == EColorblindMode::Deuteranopia);
        TLS_CHECK(!R.RumorJournalAuto());
        TLS_CHECK(R.Binding("Journal") == "K");
        TLS_CHECK_MSG(JsonSerialize(R.SerializeState(), false) == Saved, "settings round trip is byte-identical");

        // corrupt payloads refused, nothing half-applied
        const char* Corrupt[] = {
                "{\"audio\":\"loud\"}",                                  // wrong type
                "{\"display\":{\"quality\":\"ultra\"}}",                 // unknown tier
                "{\"accessibility\":{\"colorblind\":\"mono\"}}",         // unknown mode
                "{\"input\":{\"A\":\"W\",\"B\":\"W\"}}",                 // two actions, one button
                "{\"input\":{\"Interact\":5}}",                          // binding not a string
                "5"                                                      // wrong root
        };
        for (const char* Bad : Corrupt)
        {
                SettingsModel F;
                JsonParseResult PB = JsonParse(Bad);
                TLS_CHECK(PB.Ok);
                std::string BadErr;
                TLS_CHECK_MSG(!F.DeserializeState(PB.Value, BadErr), std::string("rejected: ") + Bad);
        }

        // settings are per-install: a WORLD save carries no settings payload
        G.NewGame();
        const std::string WorldSave = G.SaveToString();
        TLS_CHECK_MSG(WorldSave.find("tls.settings.v1") == std::string::npos, "world saves stay settings-free");
        TLS_CHECK_MSG(WorldSave.find("\"quality\"") == std::string::npos, "no quality key leaks into world saves");

        // Game-side consumer: the journal policy toggle is real
        G.SettingsMut().SetRumorJournalAuto(false);
        {
                const size_t Before = G.Journal().size();
                G.NotifyPlayerHeardRumor("RUM-GUINEA-SILENCE", "T3-05");
                TLS_CHECK_MSG(G.Journal().size() == Before, "auto-journal off: hearing a rumor adds no journal line");
        }
        G.SettingsMut().SetRumorJournalAuto(true);
        {
                const size_t Before = G.Journal().size();
                G.NotifyPlayerHeardRumor("RUM-EDMUND-BROUGHT", "T3-04");
                TLS_CHECK_MSG(G.Journal().size() == Before + 1, "auto-journal on: the rumor lands in the journal");
        }
}

} // anonymous namespace

namespace tls_test_settings
{

void RunAll(Game& G)
{
        TestVolumesAndClamping();
        TestQualityTierBudget();
        TestColorblindPalettes();
        TestTextScale();
        TestInputBindings();
        TestSettingsPersistence(G);
}

} // namespace tls_test_settings
