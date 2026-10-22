// THE LAST SIN: The Sin-Eater - M1
// TLSCoreTypes.cpp - enum parsing/printing + Welsh-layer text rendering.

#include "TLSCoreTypes.h"

namespace tls
{

const char* ToString(EEvidenceType T)
{
        switch (T)
        {
        case EEvidenceType::Physical: return "physical";
        case EEvidenceType::Testimonial: return "testimonial";
        case EEvidenceType::Documentary: return "documentary";
        case EEvidenceType::Hearsay: return "hearsay";
        }
        return "?";
}

const char* ToString(ETone T)
{
        switch (T)
        {
        case ETone::Gentle: return "gentle";
        case ETone::Formal: return "formal";
        case ETone::Pressing: return "pressing";
        case ETone::Silent: return "silent";
        }
        return "?";
}

const char* ToString(ETaskType T)
{
        switch (T)
        {
        case ETaskType::Reach: return "reach";
        case ETaskType::Observe: return "observe";
        case ETaskType::Collect: return "collect";
        case ETaskType::Inspect: return "inspect";
        case ETaskType::Restore: return "restore";
        case ETaskType::Dialogue: return "dialogue";
        case ETaskType::Flag: return "flag";
        case ETaskType::Insight: return "insight";
        case ETaskType::NpcRumor: return "npc_rumor";
        case ETaskType::PlayerRumor: return "player_rumor";
        case ETaskType::TensionBelow: return "tension_below";
        }
        return "?";
}

const char* ToString(EQuestStatus S)
{
        switch (S)
        {
        case EQuestStatus::NotStarted: return "not_started";
        case EQuestStatus::Active: return "active";
        case EQuestStatus::Completed: return "completed";
        case EQuestStatus::Failed: return "failed";
        }
        return "?";
}

const char* ToString(ETimeOfDay T)
{
        switch (T)
        {
        case ETimeOfDay::Morning: return "morning";
        case ETimeOfDay::Noon: return "noon";
        case ETimeOfDay::Afternoon: return "afternoon";
        case ETimeOfDay::Evening: return "evening";
        case ETimeOfDay::Night: return "night";
        }
        return "?";
}

const char* ToString(EWeather W)
{
        switch (W)
        {
        case EWeather::OvercastFog: return "overcast_fog";
        case EWeather::Rain: return "rain";
        }
        return "?";
}

const char* ToString(EReaction R)
{
        switch (R)
        {
        case EReaction::Accept: return "accept";
        case EReaction::Deny: return "deny";
        case EReaction::Break: return "break";
        }
        return "?";
}

bool ParseEvidenceType(const std::string& S, EEvidenceType& Out)
{
        if (S == "physical") { Out = EEvidenceType::Physical; return true; }
        if (S == "testimonial") { Out = EEvidenceType::Testimonial; return true; }
        if (S == "documentary") { Out = EEvidenceType::Documentary; return true; }
        if (S == "hearsay") { Out = EEvidenceType::Hearsay; return true; }
        return false;
}

bool ParseTone(const std::string& S, ETone& Out)
{
        if (S == "gentle") { Out = ETone::Gentle; return true; }
        if (S == "formal") { Out = ETone::Formal; return true; }
        if (S == "pressing") { Out = ETone::Pressing; return true; }
        if (S == "silent") { Out = ETone::Silent; return true; }
        return false;
}

bool ParseTaskType(const std::string& S, ETaskType& Out)
{
        if (S == "reach") { Out = ETaskType::Reach; return true; }
        if (S == "observe") { Out = ETaskType::Observe; return true; }
        if (S == "collect") { Out = ETaskType::Collect; return true; }
        if (S == "inspect") { Out = ETaskType::Inspect; return true; }
        if (S == "restore") { Out = ETaskType::Restore; return true; }
        if (S == "dialogue") { Out = ETaskType::Dialogue; return true; }
        if (S == "flag") { Out = ETaskType::Flag; return true; }
        if (S == "insight") { Out = ETaskType::Insight; return true; }
        if (S == "npc_rumor") { Out = ETaskType::NpcRumor; return true; }
        if (S == "player_rumor") { Out = ETaskType::PlayerRumor; return true; }
        if (S == "tension_below") { Out = ETaskType::TensionBelow; return true; }
        return false;
}

bool ParseTimeOfDay(const std::string& S, ETimeOfDay& Out)
{
        if (S == "morning") { Out = ETimeOfDay::Morning; return true; }
        if (S == "noon") { Out = ETimeOfDay::Noon; return true; }
        if (S == "afternoon") { Out = ETimeOfDay::Afternoon; return true; }
        if (S == "evening") { Out = ETimeOfDay::Evening; return true; }
        if (S == "night") { Out = ETimeOfDay::Night; return true; }
        return false;
}

bool ParseWeather(const std::string& S, EWeather& Out)
{
        if (S == "overcast_fog") { Out = EWeather::OvercastFog; return true; }
        if (S == "rain") { Out = EWeather::Rain; return true; }
        return false;
}

bool ParseReaction(const std::string& S, EReaction& Out)
{
        if (S == "accept") { Out = EReaction::Accept; return true; }
        if (S == "deny") { Out = EReaction::Deny; return true; }
        if (S == "break") { Out = EReaction::Break; return true; }
        return false;
}

std::string RenderDialogueText(const std::string& Text, int PlayerWelshLevel, bool& OutNeedsLesson)
{
        OutNeedsLesson = false;
        std::string Out;
        Out.reserve(Text.size());
        size_t I = 0;
        while (I < Text.size())
        {
                // marker form: [wN:word]  where N in 1..3
                if (Text[I] == '[' && I + 1 < Text.size() && Text[I + 1] == 'w'
                        && I + 2 < Text.size() && Text[I + 2] >= '1' && Text[I + 2] <= '3'
                        && I + 3 < Text.size() && Text[I + 3] == ':')
                {
                        const int LevelNeeded = Text[I + 2] - '0';
                        size_t J = I + 4;
                        std::string Word;
                        while (J < Text.size() && Text[J] != ']')
                        {
                                Word.push_back(Text[J]);
                                ++J;
                        }
                        if (J < Text.size()) // found closing bracket
                        {
                                if (PlayerWelshLevel >= LevelNeeded)
                                {
                                        Out += Word;
                                        Out += " (Welsh)";
                                }
                                else
                                {
                                        for (size_t K = 0; K < Word.size(); ++K)
                                        {
                                                const char C = Word[K];
                                                const bool Keep = (C == ' ' || C == '-' || C == '\'');
                                                Out.push_back(Keep ? C : '#');
                                        }
                                        OutNeedsLesson = true;
                                }
                                I = J + 1;
                                continue;
                        }
                }
                Out.push_back(Text[I]);
                ++I;
        }
        return Out;
}

} // namespace tls
