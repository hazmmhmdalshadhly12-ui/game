// THE LAST SIN: The Sin-Eater - M1
// TLSDialogue.cpp

#include "TLSDialogue.h"

namespace tls
{

namespace
{
        bool ParseConditionsFrom(const JsonValue* V, DialogueConditions& Out)
        {
                if (!V || !V->IsObject()) { return true; }
                if (const JsonValue* F = V->Find("flags"))
                {
                        for (const auto& KV : F->AsObject()) { Out.Flags[KV.first] = KV.second.IsNumber() ? KV.second.AsInt() : 1; }
                }
                Out.TrustMin = V->GetInt("trust_min", -100);
                Out.TrustMax = V->GetInt("trust_max", 100);
                Out.HasEvidence = V->GetStringList("has_evidence");
                Out.KnowsInsight = V->GetStringList("knows_insight");
                Out.WelshLevelMin = V->GetInt("welsh_level_min", 0);
                Out.DayMin = V->GetInt("day_min", 1);
                Out.DayMax = V->GetInt("day_max", 9);
                Out.QuestDone = V->GetStringList("quest_done");
                return true;
        }

        bool ParseEffectsFrom(const JsonValue* V, DialogueEffects& Out)
        {
                if (!V || !V->IsObject()) { return true; }
                Out.TrustDelta = V->GetNumber("trust_delta", 0.0);
                if (const JsonValue* F = V->Find("set_flags"))
                {
                        for (const auto& KV : F->AsObject()) { Out.SetFlags[KV.first] = KV.second.IsNumber() ? KV.second.AsInt() : 1; }
                }
                Out.GiveEvidence = V->GetStringList("give_evidence");
                Out.GiveInsight = V->GetStringList("give_insight");
                Out.RevealFacts = V->GetStringList("reveal_facts");
                Out.ReputationDelta = V->GetNumber("reputation_delta", 0.0);
                Out.TensionDelta = V->GetNumber("tension_delta", 0.0);
                Out.bAdvanceToEvening = V->GetBool("advance_to_evening", false);
                return true;
        }
}

bool DialogueSystem::Load(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "dialogue root must be an object"; return false; }
        DialogueDef Def;
        Def.Id = Root.GetString("id", "");
        Def.NpcId = Root.GetString("npc", "");
        Def.Root = Root.GetString("root", "");
        if (Def.Id.empty()) { OutError = "dialogue missing id"; return false; }
        if (Def.NpcId.empty()) { OutError = "dialogue " + Def.Id + " missing npc"; return false; }
        if (Def.Root.empty()) { OutError = "dialogue " + Def.Id + " missing root"; return false; }

        const JsonValue* Nodes = Root.Find("nodes");
        if (!Nodes || !Nodes->IsArray() || Nodes->Size() == 0) { OutError = "dialogue " + Def.Id + " has no nodes"; return false; }

        for (size_t I = 0; I < Nodes->Size(); ++I)
        {
                const JsonValue* N = Nodes->At(I);
                if (!N || !N->IsObject()) { OutError = "node not an object in " + Def.Id; return false; }
                DialogueNode Node;
                Node.Id = N->GetString("id", "");
                Node.Speaker = N->GetString("speaker", Def.NpcId);
                Node.Text = N->GetString("text", "");
                Node.Next = N->GetString("next", "");
                if (Node.Id.empty()) { OutError = "node missing id in " + Def.Id; return false; }
                if (Node.Text.empty()) { OutError = "node " + Node.Id + " has no text"; return false; }

                if (!ParseEffectsFrom(N->Find("on_enter"), Node.OnEnter)) { OutError = "bad on_enter in " + Node.Id; return false; }

                if (const JsonValue* Choices = N->Find("choices"))
                {
                        for (size_t C = 0; C < Choices->Size(); ++C)
                        {
                                const JsonValue* Cj = Choices->At(C);
                                if (!Cj || !Cj->IsObject()) { OutError = "choice not an object in " + Node.Id; return false; }
                                DialogueChoice Choice;
                                Choice.Id = Cj->GetString("id", "");
                                Choice.Text = Cj->GetString("text", "");
                                Choice.PresentEvidence = Cj->GetString("present_evidence", "");
                                if (Choice.Id.empty()) { OutError = "choice missing id in node " + Node.Id; return false; }
                                if (Choice.Text.empty()) { OutError = "choice " + Choice.Id + " has no text"; return false; }
                                std::string ToneStr = Cj->GetString("tone", "formal");
                                if (!ParseTone(ToneStr, Choice.Tone)) { OutError = "bad tone '" + ToneStr + "' in choice " + Choice.Id; return false; }
                                std::string ReactionStr = Cj->GetString("reaction", "");
                                if (!ReactionStr.empty() && !ParseReaction(ReactionStr, Choice.Reaction)) { OutError = "bad reaction '" + ReactionStr + "' in choice " + Choice.Id; return false; }
                                Choice.bOptionalHint = Cj->GetBool("optional_hint", false);
                                if (!ParseConditionsFrom(Cj->Find("conditions"), Choice.Conditions)) { OutError = "bad conditions in choice " + Choice.Id; return false; }
                                if (!ParseEffectsFrom(Cj->Find("effects"), Choice.Effects)) { OutError = "bad effects in choice " + Choice.Id; return false; }
                                Choice.Next = Cj->GetString("next", "");
                                Node.Choices.push_back(Choice);
                        }
                }
                if (Node.Choices.empty() && Node.Next.empty())
                {
                        // a terminal leaf - allowed (dialogue ends here)
                }
                if (!Node.Choices.empty() && !Node.Next.empty())
                {
                        OutError = "node " + Node.Id + " has both choices and auto-next";
                        return false;
                }
                Def.Nodes[Node.Id] = Node;
        }

        if (!Def.Nodes.count(Def.Root)) { OutError = "dialogue " + Def.Id + " root node missing"; return false; }

        // graph integrity: every next/choice target must exist
        for (const auto& KV : Def.Nodes)
        {
                if (!KV.second.Next.empty() && !Def.Nodes.count(KV.second.Next))
                {
                        OutError = "node " + KV.first + " auto-next points to missing node " + KV.second.Next;
                        return false;
                }
                for (const DialogueChoice& C : KV.second.Choices)
                {
                        if (!C.Next.empty() && !Def.Nodes.count(C.Next))
                        {
                                OutError = "choice " + C.Id + " points to missing node " + C.Next;
                                return false;
                        }
                }
        }

        Dialogues[Def.Id] = Def;
        return true;
}

const DialogueDef* DialogueSystem::FindDef(const std::string& Id) const
{
        auto It = Dialogues.find(Id);
        return It == Dialogues.end() ? nullptr : &It->second;
}

bool DialogueSystem::EvaluateConditions(const DialogueConditions& C, const IGameContext& Ctx,
        const std::string& NpcId)
{
        for (const auto& KV : C.Flags)
        {
                if (Ctx.GetFlag(KV.first) != KV.second) { return false; }
        }
        const double Trust = Ctx.GetTrust(NpcId);
        if (Trust < C.TrustMin || Trust > C.TrustMax) { return false; }
        for (const std::string& Ev : C.HasEvidence)
        {
                if (!Ctx.EvidenceCollected(Ev)) { return false; }
        }
        for (const std::string& In : C.KnowsInsight)
        {
                if (!Ctx.InsightKnown(In)) { return false; }
        }
        if (Ctx.GetWelshLevel() < C.WelshLevelMin) { return false; }
        const int Day = Ctx.CurrentDay();
        if (Day < C.DayMin || Day > C.DayMax) { return false; }
        for (const std::string& Q : C.QuestDone)
        {
                if (!Ctx.IsQuestCompleted(Q)) { return false; }
        }
        return true;
}

bool DialogueSystem::Start(const std::string& DialogueId, std::string& OutError)
{
        auto It = Dialogues.find(DialogueId);
        if (It == Dialogues.end()) { OutError = "unknown dialogue " + DialogueId; return false; }
        ActiveDialogueId = DialogueId;
        CurrentNodeId = It->second.Root;
        return true;
}

void DialogueSystem::EndSession()
{
        ActiveDialogueId.clear();
        CurrentNodeId.clear();
}

const DialogueNode* DialogueSystem::CurrentNode() const
{
        if (ActiveDialogueId.empty()) { return nullptr; }
        auto It = Dialogues.find(ActiveDialogueId);
        if (It == Dialogues.end()) { return nullptr; }
        auto NodeIt = It->second.Nodes.find(CurrentNodeId);
        return NodeIt == It->second.Nodes.end() ? nullptr : &NodeIt->second;
}

std::vector<const DialogueChoice*> DialogueSystem::AvailableChoices(const IGameContext& Ctx) const
{
        std::vector<const DialogueChoice*> Out;
        const DialogueNode* Node = CurrentNode();
        if (!Node) { return Out; }
        const DialogueDef* Def = FindDef(ActiveDialogueId);
        if (!Def) { return Out; }
        for (const DialogueChoice& C : Node->Choices)
        {
                if (EvaluateConditions(C.Conditions, Ctx, Def->NpcId)) { Out.push_back(&C); }
        }
        return Out;
}

bool DialogueSystem::Choose(size_t IndexInAvailable, const IGameContext& Ctx, ChoiceResult& Out, std::string& OutError)
{
        std::vector<const DialogueChoice*> Avail = AvailableChoices(Ctx);
        if (IndexInAvailable >= Avail.size()) { OutError = "choice index out of range"; return false; }
        Out.Choice = Avail[IndexInAvailable];
        Out.NextNodeId = Out.Choice->Next;
        if (!Out.NextNodeId.empty())
        {
                const DialogueDef* Def = FindDef(ActiveDialogueId);
                if (!Def || !Def->Nodes.count(Out.NextNodeId))
                {
                        OutError = "choice " + Out.Choice->Id + " points to missing node " + Out.NextNodeId;
                        return false;
                }
                CurrentNodeId = Out.NextNodeId;
        }
        else
        {
                MarkEnded();
        }
        return true;
}

std::string DialogueSystem::AutoNext() const
{
        const DialogueNode* Node = CurrentNode();
        return Node ? Node->Next : std::string();
}

const DialogueNode* DialogueSystem::EnterNode(const std::string& NodeId)
{
        if (ActiveDialogueId.empty()) { return nullptr; }
        auto It = Dialogues.find(ActiveDialogueId);
        if (It == Dialogues.end()) { return nullptr; }
        auto NodeIt = It->second.Nodes.find(NodeId);
        if (NodeIt == It->second.Nodes.end()) { return nullptr; }
        CurrentNodeId = NodeId;
        return &NodeIt->second;
}

bool DialogueSystem::ValidateGraph(const std::string& DialogueId, std::string& OutError) const
{
        auto It = Dialogues.find(DialogueId);
        const DialogueDef* Def = (It == Dialogues.end()) ? nullptr : &It->second;
        // during Load the def is not yet inserted - validate the local copy through CurrentNode path
        if (!Def)
        {
                // Load-time validation: the def being built is validated by the caller;
                // here we can only validate already-loaded dialogues.
                return true;
        }
        for (const auto& KV : Def->Nodes)
        {
                if (!KV.second.Next.empty() && !Def->Nodes.count(KV.second.Next))
                {
                        OutError = "node " + KV.first + " auto-next points to missing node " + KV.second.Next;
                        return false;
                }
                for (const DialogueChoice& C : KV.second.Choices)
                {
                        if (!C.Next.empty() && !Def->Nodes.count(C.Next))
                        {
                                OutError = "choice " + C.Id + " points to missing node " + C.Next;
                                return false;
                        }
                }
        }
        return true;
}

} // namespace tls
