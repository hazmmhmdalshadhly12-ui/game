// THE LAST SIN: The Sin-Eater - M1
// TLSGameState.cpp

#include "TLSGameState.h"

#include <cstdlib>

namespace tls
{

Game::Game()
{
        EvidenceSys = new EvidenceSystem();
        QuestSys = new QuestSystem();
        VillageSys = new VillageState();
        DialogueSys = new DialogueSystem();
}

Game::~Game()
{
        delete EvidenceSys;
        delete QuestSys;
        delete VillageSys;
        delete DialogueSys;
}

bool Game::LoadEvidenceData(const JsonValue& Root, std::string& OutError)
{
        if (!EvidenceSys->Load(Root, OutError)) { return false; }
        bDataLoaded = true;
        return true;
}

bool Game::LoadQuestData(const JsonValue& Root, std::string& OutError)
{
        return QuestSys->Load(Root, OutError);
}

bool Game::LoadSimData(const JsonValue& Root, std::string& OutError)
{
        return VillageSys->Load(Root, OutError);
}

bool Game::LoadDialogueData(const JsonValue& Root, std::string& OutError)
{
        return DialogueSys->Load(Root, OutError);
}

void Game::NewGame()
{
        FlagValues.clear();
        ReachedAreas.clear();
        DialogueHistory.clear();
        JournalEntries.clear();

        // reset runtime state of the subsystems (defs stay)
        {
        std::string Ignored;
        JsonValue Empty = JsonValue::MakeObject();
        EvidenceSys->DeserializeState(Empty, Ignored);
        QuestSys->DeserializeState(Empty, Ignored);
        VillageSys->ResetToDayOne();
        }

        FlagValues["FLG_EDMUND_WELSH_LEVEL"] = 0;

        JournalEntries.push_back({ 1, "Day 1. The coach left me at the bridge. Father is to be buried at noon - a sin-eater's funeral. I have not seen him in seventeen years." });

        QuestSys->ActivateDue(*this);
        RefreshAfterChange();
}

int Game::GetFlag(const std::string& FlagId) const
{
        auto It = FlagValues.find(FlagId);
        return It == FlagValues.end() ? 0 : It->second;
}

bool Game::DialogueNodeSeen(const std::string& DialogueId, const std::string& NodeId) const
{
        auto It = DialogueHistory.find(DialogueId);
        if (It == DialogueHistory.end()) { return false; }
        if (NodeId.empty()) { return !It->second.empty(); }
        return It->second.count(NodeId) != 0;
}

void Game::AddJournalEntry(const std::string& Text)
{
        JournalEntries.push_back({ VillageSys->Day(), Text });
}

void Game::ApplyEffects(const DialogueEffects& Effects, const std::string& NpcId, ETone Tone)
{
        if (Effects.TrustDelta != 0.0)
        {
                VillageSys->ApplyTrustDelta(NpcId, Effects.TrustDelta, Tone);
        }
        for (const auto& KV : Effects.SetFlags)
        {
                FlagValues[KV.first] = KV.second;
        }
        for (const std::string& Ev : Effects.GiveEvidence)
        {
                EvidenceSys->NotifyCollected(Ev, VillageSys->Day(), "sworn statement (" + NpcId + ")");
        }
        for (const std::string& In : Effects.GiveInsight)
        {
                if (EvidenceSys->ForceInsight(In))
                {
                        AddJournalEntry("The ledger saw it before I did: " + In);
                }
        }
        if (Effects.ReputationDelta != 0.0) { VillageSys->ApplyReputationDelta(Effects.ReputationDelta); }
        if (Effects.TensionDelta != 0.0) { VillageSys->ApplyTensionDelta(Effects.TensionDelta); }
        if (Effects.bAdvanceToEvening) { VillageSys->AdvanceToEvening(); }
}

void Game::ApplyQuestCompletionFlags(const std::vector<std::string>& CompletedQuestIds)
{
        for (const std::string& QId : CompletedQuestIds)
        {
                const QuestDef* Def = QuestSys->FindDef(QId);
                if (!Def) { continue; }
                for (const auto& KV : Def->FlagsOnComplete)
                {
                        FlagValues[KV.first] = KV.second;
                }
                AddJournalEntry("Done: " + Def->Title + " (" + Def->Chapter + ")");
        }
}

void Game::RefreshAfterChange()
{
        std::vector<std::string> Completed = QuestSys->Refresh(*this);
        if (!Completed.empty())
        {
                ApplyQuestCompletionFlags(Completed);
                // completion may unlock flags that satisfy other tasks - one more pass
                std::vector<std::string> More = QuestSys->Refresh(*this);
                ApplyQuestCompletionFlags(More);
        }
}

void Game::NotifyReachArea(const std::string& AreaId)
{
        ReachedAreas.insert(AreaId);
        RefreshAfterChange();
}

void Game::NotifyObserveEvidence(const std::string& Id, std::string* OutNote)
{
        std::string Note;
        EvidenceSys->NotifyObserved(Id, VillageSys->Day(), &Note);
        if (OutNote) { *OutNote = Note; }
        RefreshAfterChange();
}

void Game::NotifyCollectEvidence(const std::string& Id, const std::string& HowAcquired)
{
        EvidenceSys->NotifyCollected(Id, VillageSys->Day(), HowAcquired);
        RefreshAfterChange();
}

void Game::NotifyExamineEvidence(const std::string& Id, std::string* OutReveal)
{
        std::string Reveal;
        EvidenceSys->NotifyExamined(Id, VillageSys->Day(), &Reveal);
        if (OutReveal) { *OutReveal = Reveal; }
        RefreshAfterChange();
}

void Game::NotifyRestorePage(const std::string& Id, std::string* OutReveal)
{
        std::string Reveal;
        EvidenceSys->NotifyRestored(Id, VillageSys->Day(), &Reveal);
        if (OutReveal) { *OutReveal = Reveal; }
        RefreshAfterChange();
}

void Game::NotifyDrawLink(const std::string& A, const std::string& B, std::string* OutMessage,
        std::vector<std::string>* OutNewInsights)
{
        std::string Message;
        std::vector<std::string> NewInsights;
        EvidenceSys->DrawLink(A, B, VillageSys->Day(), Message, NewInsights);
        if (OutMessage) { *OutMessage = Message; }
        if (OutNewInsights) { *OutNewInsights = NewInsights; }
        for (const std::string& In : NewInsights)
        {
                const InsightDef* Def = EvidenceSys->FindInsight(In);
                AddJournalEntry("Insight: " + (Def ? Def->Name : In));
        }
        RefreshAfterChange();
}

void Game::NotifyDecision(const std::string& FlagId, int Value)
{
        FlagValues[FlagId] = Value;
        RefreshAfterChange();
}

bool Game::NotifySleep(std::string& OutReason)
{
        const int Day = VillageSys->Day();
        if (Day == 1 && QuestSys->Status("Q-M-C1") != EQuestStatus::Completed)
        {
                OutReason = "The day is not done - the ledger will not sleep for me yet.";
                return false;
        }
        if (Day >= 2)
        {
                OutReason = "The fog beyond the second morning is not yet written. (M1 slice boundary)";
                return false;
        }
        const int NextDay = Day + 1;
        VillageSys->BeginDay(NextDay);
        AddJournalEntry("Day " + std::to_string(NextDay) + ". The village wakes to " + std::string(ToString(VillageSys->Weather())) + ".");
        QuestSys->ActivateDue(*this);
        RefreshAfterChange();
        return true;
}

// ------------------------------------------------------------ dialogue

bool Game::BeginDialogue(const std::string& DialogueId, std::string& OutError)
{
        if (!DialogueSys->Start(DialogueId, OutError)) { return false; }
        const DialogueDef* Def = DialogueSys->FindDef(DialogueId);
        if (!Def) { OutError = "dialogue def vanished"; return false; }
        std::string Entered;
        EnterNodeAndApply(Def->Root, Entered);
        return true;
}

bool Game::DialogueRunning() const
{
        return DialogueSys->IsActive();
}

const DialogueNode* Game::DialogueCurrentNode() const
{
        return DialogueSys->CurrentNode();
}

std::vector<const DialogueChoice*> Game::DialogueAvailableChoices() const
{
        return DialogueSys->AvailableChoices(*this);
}

std::string Game::DialogueRenderedText(bool& OutNeedsLesson) const
{
        const DialogueNode* Node = DialogueSys->CurrentNode();
        if (!Node) { OutNeedsLesson = false; return ""; }
        return RenderDialogueText(Node->Text, GetWelshLevel(), OutNeedsLesson);
}

void Game::EnterNodeAndApply(const std::string& NodeId, std::string& OutEnteredNodeId)
{
        const DialogueDef* Def = DialogueSys->FindDef(DialogueSys->ActiveDialogue());
        if (!Def) { OutEnteredNodeId.clear(); return; }
        const DialogueNode* Node = DialogueSys->EnterNode(NodeId);
        if (!Node) { OutEnteredNodeId.clear(); return; }
        OutEnteredNodeId = NodeId;
        DialogueHistory[Def->Id].insert(NodeId);
        ApplyEffects(Node->OnEnter, Def->NpcId, ETone::Silent);
}

bool Game::PickDialogueChoice(size_t IndexInAvailable, std::string& OutEnteredNodeId, std::string& OutError)
{
        if (!DialogueSys->IsActive()) { OutError = "no dialogue running"; return false; }
        const DialogueDef* Def = DialogueSys->FindDef(DialogueSys->ActiveDialogue());
        if (!Def) { OutError = "no dialogue def"; return false; }

        DialogueSystem::ChoiceResult Result;
        if (!DialogueSys->Choose(IndexInAvailable, *this, Result, OutError)) { return false; }

        const DialogueChoice* Choice = Result.Choice;

        // evidence presentation reactions (QUEST_ARCHITECTURE 5)
        if (!Choice->PresentEvidence.empty())
        {
                const std::string NpcName = Def->NpcId;
                if (Choice->Reaction == EReaction::Deny)
                {
                        EvidenceSys->AppendChainNote(Choice->PresentEvidence,
                                "day " + std::to_string(VillageSys->Day()) + ": " + NpcName + " denied it (contradiction recorded)");
                }
                else if (Choice->Reaction == EReaction::Break)
                {
                        EvidenceSys->AppendChainNote(Choice->PresentEvidence,
                                "day " + std::to_string(VillageSys->Day()) + ": " + NpcName + " broke and answered");
                }
                else
                {
                        EvidenceSys->AppendChainNote(Choice->PresentEvidence,
                                "day " + std::to_string(VillageSys->Day()) + ": " + NpcName + " took the card and answered");
                }
        }

        ApplyEffects(Choice->Effects, Def->NpcId, Choice->Tone);

        if (Result.NextNodeId.empty())
        {
                DialogueSys->MarkEnded();
                OutEnteredNodeId.clear();
        }
        else
        {
                EnterNodeAndApply(Result.NextNodeId, OutEnteredNodeId);
                // auto-continue chains (nodes without choices)
                int Guard = 0;
                while (DialogueSys->IsActive())
                {
                        const DialogueNode* Node = DialogueSys->CurrentNode();
                        if (!Node || !Node->Choices.empty()) { break; }
                        if (Node->Next.empty()) { DialogueSys->MarkEnded(); OutEnteredNodeId.clear(); break; }
                        EnterNodeAndApply(Node->Next, OutEnteredNodeId);
                        if (++Guard > 32) { break; }   // cycle guard
                }
        }
        RefreshAfterChange();
        return true;
}

bool Game::DialogueAutoAdvance(std::string& OutEnteredNodeId)
{
        if (!DialogueSys->IsActive()) { return false; }
        const DialogueNode* Node = DialogueSys->CurrentNode();
        if (!Node || Node->Next.empty()) { return false; }
        EnterNodeAndApply(Node->Next, OutEnteredNodeId);
        RefreshAfterChange();
        return true;
}

// ------------------------------------------------------------ save/load

JsonValue Game::Save() const
{
        JsonValue Root = JsonValue::MakeObject();
        Root.Set("save_version", JsonValue(1));
        Root.Set("village", VillageSys->SerializeState());
        Root.Set("evidence", EvidenceSys->SerializeState());
        Root.Set("quests", QuestSys->SerializeState());

        JsonValue Flags = JsonValue::MakeObject();
        for (const auto& KV : FlagValues) { Flags.Set(KV.first, JsonValue(KV.second)); }
        Root.Set("flags", std::move(Flags));

        JsonValue Areas = JsonValue::MakeArray();
        for (const std::string& A : ReachedAreas) { Areas.Append(JsonValue(A)); }
        Root.Set("reached_areas", std::move(Areas));

        JsonValue History = JsonValue::MakeObject();
        for (const auto& KV : DialogueHistory)
        {
                JsonValue Nodes = JsonValue::MakeArray();
                for (const std::string& N : KV.second) { Nodes.Append(JsonValue(N)); }
                History.Set(KV.first, std::move(Nodes));
        }
        Root.Set("dialogue_history", std::move(History));

        JsonValue Journal = JsonValue::MakeArray();
        for (const JournalEntry& E : JournalEntries)
        {
                JsonValue J = JsonValue::MakeObject();
                J.Set("day", JsonValue(E.Day));
                J.Set("text", JsonValue(E.Text));
                Journal.Append(std::move(J));
        }
        Root.Set("journal", std::move(Journal));

        return Root;
}

std::string Game::SaveToString() const
{
        return JsonSerialize(Save(), false);
}

bool Game::LoadFromString(const std::string& Payload, std::string& OutError)
{
        JsonParseResult P = JsonParse(Payload);
        if (!P.Ok) { OutError = "save payload is not valid JSON: " + P.Error; return false; }
        const JsonValue& Root = P.Value;
        if (!Root.IsObject()) { OutError = "save root not an object"; return false; }

        const JsonValue* V = Root.Find("village");
        if (!V || !VillageSys->DeserializeState(*V, OutError)) { OutError = "village: " + OutError; return false; }
        const JsonValue* E = Root.Find("evidence");
        if (!E || !EvidenceSys->DeserializeState(*E, OutError)) { OutError = "evidence: " + OutError; return false; }
        const JsonValue* Q = Root.Find("quests");
        if (!Q || !QuestSys->DeserializeState(*Q, OutError)) { OutError = "quests: " + OutError; return false; }

        FlagValues.clear();
        if (const JsonValue* F = Root.Find("flags"))
        {
                for (const auto& KV : F->AsObject()) { FlagValues[KV.first] = KV.second.AsInt(); }
        }
        ReachedAreas.clear();
        if (const JsonValue* A = Root.Find("reached_areas"))
        {
                for (size_t I = 0; I < A->Size(); ++I)
                {
                        if (const JsonValue* Item = A->At(I)) { ReachedAreas.insert(Item->AsString()); }
                }
        }
        DialogueHistory.clear();
        if (const JsonValue* H = Root.Find("dialogue_history"))
        {
                for (const auto& KV : H->AsObject())
                {
                        std::set<std::string> Nodes;
                        for (size_t I = 0; I < KV.second.Size(); ++I)
                        {
                                if (const JsonValue* N = KV.second.At(I)) { Nodes.insert(N->AsString()); }
                        }
                        DialogueHistory[KV.first] = Nodes;
                }
        }
        JournalEntries.clear();
        if (const JsonValue* J = Root.Find("journal"))
        {
                for (size_t I = 0; I < J->Size(); ++I)
                {
                        const JsonValue* Entry = J->At(I);
                        if (!Entry) { continue; }
                        JournalEntry JE;
                        JE.Day = Entry->GetInt("day", 1);
                        JE.Text = Entry->GetString("text", "");
                        JournalEntries.push_back(JE);
                }
        }

        // an interrupted dialogue is not part of a save (save happens at the desk)
        DialogueSys->EndSession();
        return true;
}

} // namespace tls
