// THE LAST SIN: The Sin-Eater - M2.4
// TLSSettings: the settings & accessibility model.
// Pure C++17, no engine includes. Every value here is consumed by a real
// system behavior in the core (journal policy, subtitle policy, sim tick
// budget, board palette tokens, input conflict validation); the UE layer
// binds presentation (mixer volumes, UMG scale, Enhanced Input) to these
// values - those bindings are engine-side work and stay honestly separate.

#pragma once

#include "TLSJson.h"

#include <map>
#include <string>

namespace tls
{

enum class EQualityTier
{
        Low,      // weak devices (dual-core iGPU): 1 gossip tick per rendered frame
        Medium,   // 2 ticks per frame
        High      // 4 ticks per frame
};

enum class EColorblindMode
{
        None,
        Deuteranopia,
        Protanopia,
        Tritanopia
};

const char* ToString(EQualityTier T);
bool ParseQualityTier(const std::string& S, EQualityTier& Out);
const char* ToString(EColorblindMode M);
bool ParseColorblindMode(const std::string& S, EColorblindMode& Out);

// Ledger-board color tokens (GAME_BIBLE 7.2 palette; accessibility modes are
// the sanctioned exception to the strict palette rule - readability first).
struct BoardPalette
{
        std::string Link;          // line between two linked evidence cards
        std::string Contradiction; // line marking a recorded contradiction
        std::string Background;    // ledger paper
        std::string Ink;           // text and card frames
};

class SettingsModel
{
public:
        SettingsModel();   // defaults

        // ---- audio (0..1, clamped - clamping IS the policy) ----
        void SetMasterVolume(double V) { Audio.Master = Clamp01(V); }
        void SetMusicVolume(double V) { Audio.Music = Clamp01(V); }
        void SetSfxVolume(double V) { Audio.Sfx = Clamp01(V); }
        void SetDialogueVolume(double V) { Audio.Dialogue = Clamp01(V); }
        double MasterVolume() const { return Audio.Master; }
        double MusicVolume() const { return Audio.Music; }
        double SfxVolume() const { return Audio.Sfx; }
        double DialogueVolume() const { return Audio.Dialogue; }

        // ---- display ----
        void SetQualityTier(EQualityTier T) { Quality = T; }
        EQualityTier GetQualityTier() const { return Quality; }
        // REAL consumer: the UE day script may advance at most this many gossip
        // hour-ticks per rendered frame (NPC_SIMULATION 10 budget discipline).
        int GossipTicksPerFrame() const;
        void SetLargeText(bool B) { bLargeText = B; }
        bool UsesLargeText() const { return bLargeText; }
        // REAL consumer: dialogue presentation scale (UMG binds font size to it).
        double TextScale() const { return bLargeText ? 1.5 : 1.0; }

        // ---- accessibility ----
        void SetColorblindMode(EColorblindMode M) { Colorblind = M; }
        EColorblindMode GetColorblindMode() const { return Colorblind; }
        // REAL consumer: the ledger board reads these tokens per mode.
        const BoardPalette& BoardColors() const;
        // REAL policy: subtitles switch on automatically when the dialogue
        // channel is quiet - the investigation must never lose its testimony.
        bool SubtitlesForced() const { return bSubtitlesAlways || Audio.Dialogue < 0.20; }
        void SetSubtitlesAlways(bool B) { bSubtitlesAlways = B; }
        bool SubtitlesAlways() const { return bSubtitlesAlways; }
        // REAL consumer: Game journals a heard rumor only when this is on.
        void SetRumorJournalAuto(bool B) { bRumorJournalAuto = B; }
        bool RumorJournalAuto() const { return bRumorJournalAuto; }

        // ---- input (keyboard+mouse and gamepad codes; conflict-checked) ----
        // Returns false when the code is already bound to another action -
        // two actions on one button is rejected, never silently remapped.
        bool SetBinding(const std::string& Action, const std::string& Code);
        std::string Binding(const std::string& Action) const;
        const std::map<std::string, std::string>& Bindings() const { return ActionToCode; }

        // ---- persistence (per-install settings file, NOT part of world saves) ----
        JsonValue SerializeState() const;
        bool DeserializeState(const JsonValue& Root, std::string& OutError);

private:
        static double Clamp01(double V) { return V < 0.0 ? 0.0 : (V > 1.0 ? 1.0 : V); }

        struct AudioSet
        {
                double Master = 1.0;
                double Music = 1.0;
                double Sfx = 1.0;
                double Dialogue = 1.0;
        } Audio;

        EQualityTier Quality = EQualityTier::Medium;
        EColorblindMode Colorblind = EColorblindMode::None;
        bool bLargeText = false;
        bool bSubtitlesAlways = false;
        bool bRumorJournalAuto = true;

        std::map<std::string, std::string> ActionToCode;
};

} // namespace tls
