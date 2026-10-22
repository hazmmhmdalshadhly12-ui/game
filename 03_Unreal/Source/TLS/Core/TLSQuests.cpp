// THE LAST SIN: The Sin-Eater - M1
// TLSQuests.cpp

#include "TLSQuests.h"

namespace tls
{

bool QuestSystem::Load(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "quests root must be an object"; return false; }
        const JsonValue* Quests = Root.Find("quests");
        if (!Quests || !Quests->IsArray()) { OutError = "missing 'quests' array"; return false; }

        for (size_t I = 0; I < Quests->Size(); ++I)
        {
                const JsonValue* Q = Quests->At(I);
                if (!Q || !Q->IsObject()) { OutError = "quest entry not an object"; return false; }
                QuestDef Def;
                Def.Id = Q->GetString("id", "");
                Def.Title = Q->GetString("title", "");
                Def.Chapter = Q->GetString("chapter", "");
                Def.DayWindowMin = Q->GetInt("day_window_min", 1);
                Def.DayWindowMax = Q->GetInt("day_window_max", 9);
                Def.bAutoStart = Q->GetBool("auto_start", true);
                if (Def.Id.empty()) { OutError = "quest missing id"; return false; }
                if (Def.DayWindowMin > Def.DayWindowMax) { OutError = "quest " + Def.Id + " inverted day window"; return false; }

                const JsonValue* Objectives = Q->Find("objectives");
                if (!Objectives || !Objectives->IsArray() || Objectives->Size() == 0)
                {
                        OutError = "quest " + Def.Id + " has no objectives";
                        return false;
                }
                for (size_t O = 0; O < Objectives->Size(); ++O)
                {
                        const JsonValue* Oj = Objectives->At(O);
                        if (!Oj || !Oj->IsObject()) { OutError = "objective not an object in " + Def.Id; return false; }
                        ObjectiveDef Obj;
                        Obj.Id = Oj->GetString("id", "");
                        Obj.Description = Oj->GetString("description", "");
                        Obj.bOptional = Oj->GetBool("optional", false);
                        if (Obj.Id.empty()) { OutError = "objective missing id in " + Def.Id; return false; }

                        const JsonValue* Tasks = Oj->Find("tasks");
                        if (!Tasks || !Tasks->IsArray() || Tasks->Size() == 0)
                        {
                                OutError = "objective " + Obj.Id + " has no tasks";
                                return false;
                        }
                        for (size_t T = 0; T < Tasks->Size(); ++T)
                        {
                                const JsonValue* Tj = Tasks->At(T);
                                if (!Tj || !Tj->IsObject()) { OutError = "task not an object in " + Obj.Id; return false; }
                                TaskDef Task;
                                std::string TypeStr = Tj->GetString("type", "");
                                if (!ParseTaskType(TypeStr, Task.Type)) { OutError = "bad task type '" + TypeStr + "' in " + Obj.Id; return false; }
                                Task.Target = Tj->GetString("target", "");
                                Task.RequiredCount = Tj->GetInt("value", 1);
                                if (Task.Target.empty()) { OutError = "task missing target in " + Obj.Id; return false; }
                                if (Task.Type == ETaskType::Dialogue && Task.Target.find(':') == std::string::npos)
                                {
                                        // bare dialogue id = "any node of that dialogue"
                                }
                                Obj.Tasks.push_back(Task);
                        }
                        Def.Objectives.push_back(Obj);
                }

                if (const JsonValue* F = Q->Find("flags_on_complete"))
                {
                        for (const auto& KV : F->AsObject()) { Def.FlagsOnComplete[KV.first] = KV.second.IsNumber() ? KV.second.AsInt() : 1; }
                }

                QuestDefs[Def.Id] = Def;
        }
        return true;
}

const QuestDef* QuestSystem::FindDef(const std::string& Id) const
{
        auto It = QuestDefs.find(Id);
        return It == QuestDefs.end() ? nullptr : &It->second;
}

const QuestRuntime* QuestSystem::FindState(const std::string& Id) const
{
        auto It = QuestStates.find(Id);
        return It == QuestStates.end() ? nullptr : &It->second;
}

EQuestStatus QuestSystem::Status(const std::string& Id) const
{
        const QuestRuntime* R = FindState(Id);
        return R ? R->Status : EQuestStatus::NotStarted;
}

bool QuestSystem::ForceActivate(const std::string& Id, int Day, std::string& OutError)
{
        auto DefIt = QuestDefs.find(Id);
        if (DefIt == QuestDefs.end()) { OutError = "unknown quest " + Id; return false; }
        QuestRuntime& R = QuestStates[Id];
        if (R.Status != EQuestStatus::NotStarted) { OutError = "quest " + Id + " already started"; return false; }
        R.Status = EQuestStatus::Active;
        R.DayStarted = Day;
        R.Objectives.assign(DefIt->second.Objectives.size(), QuestObjectiveState());
        for (size_t O = 0; O < DefIt->second.Objectives.size(); ++O)
        {
                R.Objectives[O].Tasks.assign(DefIt->second.Objectives[O].Tasks.size(), QuestTaskState());
        }
        return true;
}

std::vector<std::string> QuestSystem::ActivateDue(const IGameContext& Context)
{
        std::vector<std::string> OutNew;
        const int Day = Context.CurrentDay();
        for (const auto& KV : QuestDefs)
        {
                const QuestDef& Def = KV.second;
                if (!Def.bAutoStart) { continue; }
                if (Day < Def.DayWindowMin || Day > Def.DayWindowMax) { continue; }
                QuestRuntime& R = QuestStates[KV.first];
                if (R.Status == EQuestStatus::NotStarted)
                {
                        R.Status = EQuestStatus::Active;
                        R.DayStarted = Day;
                        R.Objectives.assign(Def.Objectives.size(), QuestObjectiveState());
                        for (size_t O = 0; O < Def.Objectives.size(); ++O)
                        {
                                R.Objectives[O].Tasks.assign(Def.Objectives[O].Tasks.size(), QuestTaskState());
                        }
                        OutNew.push_back(KV.first);
                }
        }
        return OutNew;
}

bool QuestSystem::EvaluateTask(const TaskDef& Task, const IGameContext& C) const
{
        switch (Task.Type)
        {
        case ETaskType::Reach: return C.HasReachedArea(Task.Target);
        case ETaskType::Observe: return C.EvidenceObserved(Task.Target);
        case ETaskType::Collect: return C.EvidenceCollected(Task.Target);
        case ETaskType::Inspect: return C.EvidenceExamined(Task.Target);
        case ETaskType::Restore: return C.EvidenceRestored(Task.Target);
        case ETaskType::Insight: return C.InsightKnown(Task.Target);
        case ETaskType::Flag: return C.GetFlag(Task.Target) == Task.RequiredCount;
        case ETaskType::Dialogue:
        {
                const size_t Colon = Task.Target.find(':');
                if (Colon == std::string::npos) { return C.DialogueNodeSeen(Task.Target, ""); }
                return C.DialogueNodeSeen(Task.Target.substr(0, Colon), Task.Target.substr(Colon + 1));
        }
        }
        return false;
}

std::vector<std::string> QuestSystem::Refresh(IGameContext& Context)
{
        std::vector<std::string> OutCompleted;

        for (auto& KV : QuestStates)
        {
                QuestRuntime& R = KV.second;
                if (R.Status != EQuestStatus::Active) { continue; }
                auto DefIt = QuestDefs.find(KV.first);
                if (DefIt == QuestDefs.end()) { continue; }
                const QuestDef& Def = DefIt->second;

                // (re)size state containers to the definitions
                if (R.Objectives.size() != Def.Objectives.size())
                {
                        R.Objectives.assign(Def.Objectives.size(), QuestObjectiveState());
                }
                for (size_t O = 0; O < Def.Objectives.size(); ++O)
                {
                        if (R.Objectives[O].Tasks.size() != Def.Objectives[O].Tasks.size())
                        {
                                R.Objectives[O].Tasks.assign(Def.Objectives[O].Tasks.size(), QuestTaskState());
                        }
                }

                bool bAllRequiredDone = true;
                for (size_t O = 0; O < Def.Objectives.size(); ++O)
                {
                        const ObjectiveDef& Obj = Def.Objectives[O];
                        QuestObjectiveState& ObjState = R.Objectives[O];
                        if (ObjState.bDone) { continue; }

                        bool bObjDone = true;
                        for (size_t T = 0; T < Obj.Tasks.size(); ++T)
                        {
                                if (!ObjState.Tasks[T].bDone)
                                {
                                        if (EvaluateTask(Obj.Tasks[T], Context)) { ObjState.Tasks[T].bDone = true; }
                                        else { bObjDone = false; }
                                }
                        }
                        if (bObjDone) { ObjState.bDone = true; }
                        if (!ObjState.bDone && !Obj.bOptional) { bAllRequiredDone = false; }
                }

                if (bAllRequiredDone)
                {
                        R.Status = EQuestStatus::Completed;
                        R.DayCompleted = Context.CurrentDay();
                        OutCompleted.push_back(KV.first);
                }
        }
        return OutCompleted;
}

std::vector<QuestSystem::QuestProgressLine> QuestSystem::ProgressLines() const
{
        std::vector<QuestProgressLine> Out;
        for (const auto& KV : QuestDefs)
        {
                const QuestDef& Def = KV.second;
                auto StateIt = QuestStates.find(KV.first);
                if (StateIt == QuestStates.end()) { continue; }
                const QuestRuntime& R = StateIt->second;
                if (R.Status == EQuestStatus::NotStarted) { continue; }

                for (size_t O = 0; O < Def.Objectives.size(); ++O)
                {
                        // include optional objectives only while the quest is active
                        if (Def.Objectives[O].bOptional && R.Status != EQuestStatus::Active) { continue; }
                        const bool bObjDone = O < R.Objectives.size() && R.Objectives[O].bDone;
                        QuestProgressLine Line;
                        Line.QuestId = Def.Id;
                        Line.Title = Def.Title;
                        Line.ObjectiveId = Def.Objectives[O].Id;
                        Line.ObjectiveText = Def.Objectives[O].Description;
                        Line.bObjectiveDone = bObjDone;
                        Line.bObjectiveOptional = Def.Objectives[O].bOptional;
                        Line.bQuestActive = R.Status == EQuestStatus::Active;
                        Out.push_back(Line);
                }
        }
        return Out;
}

JsonValue QuestSystem::SerializeState() const
{
        JsonValue Root = JsonValue::MakeObject();
        JsonValue Arr = JsonValue::MakeArray();
        for (const auto& KV : QuestStates)
        {
                JsonValue Q = JsonValue::MakeObject();
                Q.Set("id", JsonValue(KV.first));
                Q.Set("status", JsonValue(std::string(ToString(KV.second.Status))));
                Q.Set("day_started", JsonValue(KV.second.DayStarted));
                Q.Set("day_completed", JsonValue(KV.second.DayCompleted));
                JsonValue Objs = JsonValue::MakeArray();
                for (const QuestObjectiveState& O : KV.second.Objectives)
                {
                        JsonValue OJ = JsonValue::MakeObject();
                        OJ.Set("done", JsonValue(O.bDone));
                        JsonValue Tasks = JsonValue::MakeArray();
                        for (const QuestTaskState& T : O.Tasks) { Tasks.Append(JsonValue(T.bDone)); }
                        OJ.Set("tasks", std::move(Tasks));
                        Objs.Append(std::move(OJ));
                }
                Q.Set("objectives", std::move(Objs));
                Arr.Append(std::move(Q));
        }
        Root.Set("quests", std::move(Arr));
        return Root;
}

bool QuestSystem::DeserializeState(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "quest state root not an object"; return false; }
        QuestStates.clear();
        const JsonValue* Arr = Root.Find("quests");
        if (!Arr) { return true; }
        for (size_t I = 0; I < Arr->Size(); ++I)
        {
                const JsonValue* Q = Arr->At(I);
                if (!Q) { continue; }
                const std::string Id = Q->GetString("id", "");
                QuestRuntime R;
                std::string StatusStr = Q->GetString("status", "not_started");
                if (StatusStr == "active") { R.Status = EQuestStatus::Active; }
                else if (StatusStr == "completed") { R.Status = EQuestStatus::Completed; }
                else { R.Status = EQuestStatus::NotStarted; }
                R.DayStarted = Q->GetInt("day_started", 0);
                R.DayCompleted = Q->GetInt("day_completed", 0);
                if (const JsonValue* Objs = Q->Find("objectives"))
                {
                        for (size_t O = 0; O < Objs->Size(); ++O)
                        {
                                const JsonValue* OJ = Objs->At(O);
                                if (!OJ) { continue; }
                                QuestObjectiveState ObjState;
                                ObjState.bDone = OJ->GetBool("done", false);
                                if (const JsonValue* Tasks = OJ->Find("tasks"))
                                {
                                        for (size_t T = 0; T < Tasks->Size(); ++T)
                                        {
                                                if (const JsonValue* Tj = Tasks->At(T)) { ObjState.Tasks.push_back(QuestTaskState{ Tj->AsBool() }); }
                                        }
                                }
                                R.Objectives.push_back(ObjState);
                        }
                }
                QuestStates[Id] = R;
        }
        return true;
}

} // namespace tls
