// THE LAST SIN: The Sin-Eater - M2.4
// TLSSettings.cpp

#include "TLSSettings.h"

namespace tls
{

const char* ToString(EQualityTier T)
{
        switch (T)
        {
        case EQualityTier::Low: return "low";
        case EQualityTier::Medium: return "medium";
        case EQualityTier::High: return "high";
        }
        return "medium";
}

bool ParseQualityTier(const std::string& S, EQualityTier& Out)
{
        if (S == "low") { Out = EQualityTier::Low; return true; }
        if (S == "medium") { Out = EQualityTier::Medium; return true; }
        if (S == "high") { Out = EQualityTier::High; return true; }
        return false;
}

const char* ToString(EColorblindMode M)
{
        switch (M)
        {
        case EColorblindMode::None: return "none";
        case EColorblindMode::Deuteranopia: return "deuteranopia";
        case EColorblindMode::Protanopia: return "protanopia";
        case EColorblindMode::Tritanopia: return "tritanopia";
        }
        return "none";
}

bool ParseColorblindMode(const std::string& S, EColorblindMode& Out)
{
        if (S == "none") { Out = EColorblindMode::None; return true; }
        if (S == "deuteranopia") { Out = EColorblindMode::Deuteranopia; return true; }
        if (S == "protanopia") { Out = EColorblindMode::Protanopia; return true; }
        if (S == "tritanopia") { Out = EColorblindMode::Tritanopia; return true; }
        return false;
}

SettingsModel::SettingsModel()
{
        // keyboard + mouse and gamepad defaults (Enhanced Input action names).
        // Codes are real UE input paths; conflict validation lives in SetBinding.
        ActionToCode["MoveForward"] = "W";
        ActionToCode["MoveBack"] = "S";
        ActionToCode["MoveLeft"] = "A";
        ActionToCode["MoveRight"] = "D";
        ActionToCode["Sprint"] = "LeftShift";
        ActionToCode["Interact"] = "E";
        ActionToCode["Journal"] = "J";
        ActionToCode["LedgerBoard"] = "Tab";
        ActionToCode["RumorLeak"] = "Q";
        ActionToCode["RumorDeny"] = "R";
        ActionToCode["Pause"] = "Escape";
        // gamepad mirrors for the actions that matter in the field
        ActionToCode["Pad_Interact"] = "Gamepad_FaceButton_Bottom";
        ActionToCode["Pad_Journal"] = "Gamepad_DPad_Left";
        ActionToCode["Pad_LedgerBoard"] = "Gamepad_Special_Right";
        ActionToCode["Pad_Pause"] = "Gamepad_Special_Left";
}

int SettingsModel::GossipTicksPerFrame() const
{
        switch (Quality)
        {
        case EQualityTier::Low: return 1;
        case EQualityTier::High: return 4;
        case EQualityTier::Medium: break;
        }
        return 2;
}

const BoardPalette& SettingsModel::BoardColors() const
{
        // token tables per mode; Background stays ledger paper (PPR #D9CBB2) and
        // Ink stays ink (#1C2226) in every mode - only the LINE colors move to
        // pairs that survive each deficiency (luminance-separated, never the
        // confused axis alone).
        static const BoardPalette Tables[4] = {
                // None: GAME_BIBLE 7.2 as drawn - candle amber vs sin-blue
                { "#E8A34D", "#7FA8C9", "#D9CBB2", "#1C2226" },
                // Deuteranopia: keep the amber, deepen the blue (luminance axis)
                { "#E8A34D", "#2E5F8A", "#D9CBB2", "#1C2226" },
                // Protanopia: brighten amber, darken blue
                { "#F0B25A", "#1F4D73", "#D9CBB2", "#1C2226" },
                // Tritanopia: blue-yellow axis is the confusion - move to rose/teal
                { "#C96A8C", "#3D7A6E", "#D9CBB2", "#1C2226" }
        };
        switch (Colorblind)
        {
        case EColorblindMode::Deuteranopia: return Tables[1];
        case EColorblindMode::Protanopia: return Tables[2];
        case EColorblindMode::Tritanopia: return Tables[3];
        case EColorblindMode::None: break;
        }
        return Tables[0];
}

bool SettingsModel::SetBinding(const std::string& Action, const std::string& Code)
{
        if (Action.empty() || Code.empty()) { return false; }
        for (const auto& KV : ActionToCode)
        {
                if (KV.second == Code && KV.first != Action) { return false; }   // one button, one action
        }
        ActionToCode[Action] = Code;
        return true;
}

std::string SettingsModel::Binding(const std::string& Action) const
{
        auto It = ActionToCode.find(Action);
        return It == ActionToCode.end() ? std::string() : It->second;
}

// ------------------------------------------------------------ persistence

JsonValue SettingsModel::SerializeState() const
{
        JsonValue Root = JsonValue::MakeObject();
        Root.Set("schema", JsonValue("tls.settings.v1"));

        JsonValue A = JsonValue::MakeObject();
        A.Set("master", JsonValue(Audio.Master));
        A.Set("music", JsonValue(Audio.Music));
        A.Set("sfx", JsonValue(Audio.Sfx));
        A.Set("dialogue", JsonValue(Audio.Dialogue));
        Root.Set("audio", std::move(A));

        JsonValue D = JsonValue::MakeObject();
        D.Set("quality", JsonValue(std::string(ToString(Quality))));
        D.Set("large_text", JsonValue(bLargeText));
        Root.Set("display", std::move(D));

        JsonValue Ac = JsonValue::MakeObject();
        Ac.Set("colorblind", JsonValue(std::string(ToString(Colorblind))));
        Ac.Set("subtitles_always", JsonValue(bSubtitlesAlways));
        Ac.Set("rumor_journal_auto", JsonValue(bRumorJournalAuto));
        Root.Set("accessibility", std::move(Ac));

        JsonValue I = JsonValue::MakeObject();
        for (const auto& KV : ActionToCode) { I.Set(KV.first, JsonValue(KV.second)); }
        Root.Set("input", std::move(I));

        return Root;
}

bool SettingsModel::DeserializeState(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "settings root not an object"; return false; }

        // validate everything first, then commit
        AudioSet NewAudio = Audio;
        if (const JsonValue* A = Root.Find("audio"))
        {
                if (!A->IsObject()) { OutError = "audio settings not an object"; return false; }
                NewAudio.Master = Clamp01(A->GetNumber("master", Audio.Master));
                NewAudio.Music = Clamp01(A->GetNumber("music", Audio.Music));
                NewAudio.Sfx = Clamp01(A->GetNumber("sfx", Audio.Sfx));
                NewAudio.Dialogue = Clamp01(A->GetNumber("dialogue", Audio.Dialogue));
        }

        EQualityTier NewQuality = Quality;
        bool NewLargeText = bLargeText;
        if (const JsonValue* D = Root.Find("display"))
        {
                if (!D->IsObject()) { OutError = "display settings not an object"; return false; }
                if (!ParseQualityTier(D->GetString("quality", ToString(Quality)), NewQuality))
                {
                        OutError = "unknown quality tier"; return false;
                }
                NewLargeText = D->GetBool("large_text", bLargeText);
        }

        EColorblindMode NewMode = Colorblind;
        bool NewSubs = bSubtitlesAlways, NewJournal = bRumorJournalAuto;
        if (const JsonValue* Ac = Root.Find("accessibility"))
        {
                if (!Ac->IsObject()) { OutError = "accessibility settings not an object"; return false; }
                if (!ParseColorblindMode(Ac->GetString("colorblind", ToString(Colorblind)), NewMode))
                {
                        OutError = "unknown colorblind mode"; return false;
                }
                NewSubs = Ac->GetBool("subtitles_always", bSubtitlesAlways);
                NewJournal = Ac->GetBool("rumor_journal_auto", bRumorJournalAuto);
        }

        std::map<std::string, std::string> NewBindings;
        if (const JsonValue* I = Root.Find("input"))
        {
                if (!I->IsObject()) { OutError = "input settings not an object"; return false; }
                for (const auto& KV : I->AsObject())
                {
                        if (!KV.second.IsString()) { OutError = "binding value not a string"; return false; }
                        NewBindings[KV.first] = KV.second.AsString();
                }
                // the payload must not carry two actions on one button
                for (auto A = NewBindings.begin(); A != NewBindings.end(); ++A)
                {
                        for (auto B = NewBindings.begin(); B != NewBindings.end(); ++B)
                        {
                                if (A != B && A->second == B->second)
                                {
                                        OutError = "two actions bound to one button: " + A->second;
                                        return false;
                                }
                        }
                }
        }

        // commit
        Audio = NewAudio;
        Quality = NewQuality;
        bLargeText = NewLargeText;
        Colorblind = NewMode;
        bSubtitlesAlways = NewSubs;
        bRumorJournalAuto = NewJournal;
        if (!NewBindings.empty())
        {
                // keep unlisted defaults, apply the payload's bindings
                for (const auto& KV : NewBindings)
                {
                        bool bConflict = false;
                        for (const auto& Existing : ActionToCode)
                        {
                                if (Existing.second == KV.second && Existing.first != KV.first
                                        && NewBindings.find(Existing.first) == NewBindings.end())
                                {
                                        bConflict = true;   // payload would steal a default binding
                                        break;
                                }
                        }
                        if (!bConflict) { ActionToCode[KV.first] = KV.second; }
                        else { OutError = "two actions bound to one button: " + KV.second; return false; }
                }
        }
        return true;
}

} // namespace tls
