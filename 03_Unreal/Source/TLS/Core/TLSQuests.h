// THE LAST SIN: The Sin-Eater - M1
// TLSQuests: quest definitions + state machine. Tasks are evaluated against
// an IGameContext implemented by the game state (areas reached, evidence
// states, flags, insights, dialogue history, current day).
// Semantics per docs/QUEST_ARCHITECTURE.md 1 (data model) and 3 (chapters).

#pragma once

#include "TLSCoreTypes.h"
#include "TLSJson.h"

#include <map>
#include <string>
#include <vector>

namespace tls
{

struct QuestTaskState
{
        bool bDone = false;
};

struct QuestObjectiveState
{
        bool bDone = false;
        std::vector<QuestTaskState> Tasks;
};

struct QuestRuntime
{
        EQuestStatus Status = EQuestStatus::NotStarted;
        std::vector<QuestObjectiveState> Objectives;   // parallel to def objectives
        int DayStarted = 0;
        int DayCompleted = 0;
};

class QuestSystem
{
public:
        bool Load(const JsonValue& Root, std::string& OutError);

        // Re-evaluates every task of every started quest against the context.
        // Returns ids of quests that transitioned to Completed during this call.
        std::vector<std::string> Refresh(IGameContext& Context);

        // M2.3: fails every Active quest whose day window closed (fails_on_expiry).
        // Returns the ids that transitioned to Failed; the caller applies the
        // def's flags_on_fail so the story carries the consequence forward.
        std::vector<std::string> ProcessExpiry(IGameContext& Context);

        // Activates auto-start quests whose day window is open.
        // Returns ids of quests that became Active during this call.
        std::vector<std::string> ActivateDue(const IGameContext& Context);

        const QuestDef* FindDef(const std::string& Id) const;
        const QuestRuntime* FindState(const std::string& Id) const;
        EQuestStatus Status(const std::string& Id) const;
        bool ForceActivate(const std::string& Id, int Day, std::string& OutError);

        // Snapshot for UI: active quests + objective progress lines.
        struct QuestProgressLine
        {
                std::string QuestId;
                std::string Title;
                std::string ObjectiveId;
                std::string ObjectiveText;
                bool bObjectiveDone;
                bool bObjectiveOptional;
                bool bQuestActive;
        };
        std::vector<QuestProgressLine> ProgressLines() const;

        JsonValue SerializeState() const;
        bool DeserializeState(const JsonValue& Root, std::string& OutError);

private:
        bool EvaluateTask(const TaskDef& Task, const IGameContext& C) const;

        std::map<std::string, QuestDef> QuestDefs;
        std::map<std::string, QuestRuntime> QuestStates;
};

} // namespace tls
