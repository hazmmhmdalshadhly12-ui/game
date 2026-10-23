// THE LAST SIN: The Sin-Eater - M1 core + M2 rumor integration
// TLSGameState.cpp

#include "TLSGameState.h"

#include <cstdio>
#include <cstdlib>

namespace tls
{

Game::Game()
{
        EvidenceSys = new EvidenceSystem();
        QuestSys = new QuestSystem();
        VillageSys = new VillageState();
        DialogueSys = new DialogueSystem();
        RumorSys = new RumorSystem();
}

Game::~Game()
{
        delete EvidenceSys;
        delete QuestSys;
        delete VillageSys;
        delete DialogueSys;
        delete RumorSys;
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

bool Game::LoadRumorData(const JsonValue& Root, std::string& OutError)
{
        return RumorSys->Load(Root, OutError);
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
        RumorSys->DeserializeState(Empty, Ignored);
        VillageSys->ResetToDayOne();
        }

        // every new game starts from the same simulation stream (M2 determinism)
        SimRngStream.Seed(kDefaultSimSeed);

        FlagValues["FLG_EDMUND_WELSH_LEVEL"] = 0;

        JournalEntries.push_back({ 1, "Day 1. The coach left me at the bridge. Father is to be buried at noon - a sin-eater's funeral. I have not seen him in seventeen years." });

        // rumors born on day 1 enter the village's mouth-to-mouth layer
        RumorSys->ActivateDue(VillageSys->Day());

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

// ------------------------------------------------------------ M2.1 rumor driving

RumorSystem::TickResult Game::TickVillageGossip(int Day, int Hour)
{
        RumorSystem::TickResult Result = RumorSys->TickHour(Day, Hour, *VillageSys, SimRngStream);
        // a rumor crossing its first mouth moves the village (tension event, once)
        for (const std::string& RumorId : Result.RumorsThatFirstSpread)
        {
                const RumorDef* Def = RumorSys->FindDef(RumorId);
                if (Def && Def->TensionOnSpread != 0.0)
                {
                        VillageSys->ApplyTensionDelta(Def->TensionOnSpread);
                }
        }
        return Result;
}

bool Game::NotifyWitnessEvent(const std::string& RumorId, int Day, int Hour, const std::string& Zone,
        const std::vector<std::string>& WitnessNpcIds, std::string& OutError)
{
        return RumorSys->RegisterWitnessEvent(RumorId, Day, Hour, Zone, WitnessNpcIds, OutError);
}

bool Game::NotifyPlayerHeardRumor(const std::string& RumorId, const std::string& FromNpc)
{
        const bool bAlreadyKnown = PlayerHeardRumor(RumorId);
        if (!RumorSys->NotifyPlayerHeard(RumorId, VillageSys->Day(), 0, FromNpc)) { return false; }
        if (!bAlreadyKnown)
        {
                // accessibility: auto-journal can be switched off (clutter assist)
                if (SettingsCfg.RumorJournalAuto())
                {
                        const RumorDef* Def = RumorSys->FindDef(RumorId);
                        if (Def) { AddJournalEntry("Heard in the village: " + Def->Variants.front()); }
                }
                RefreshAfterChange();
        }
        return true;
}

int Game::NotifyPlayerRumorDenial()
{
        const int Affected = RumorSys->NotifyPlayerDenial(VillageSys->Day(), 0);
        if (Affected > 0)
        {
                // the rational villager's tool: the village rewards a public stand (NPC_SIMULATION 5)
                VillageSys->ApplyReputationDelta(2.0);
                AddJournalEntry("I named the Hunger a lie, out loud. Some nodded. Some did not.");
        }
        return Affected;
}

int Game::NotifyPlayerLeakRumor(const std::string& RumorId, const std::string& Zone, std::string& OutError)
{
        const int Heard = RumorSys->NotifyPlayerLeak(RumorId, VillageSys->Day(), 12, Zone, *VillageSys, OutError);
        if (Heard > 0)
        {
                // the player knows what they are spreading
                RumorSys->NotifyPlayerHeard(RumorId, VillageSys->Day(), 12, "PLAYER");
                AddJournalEntry("I let it slip where ears were waiting. No name attached to it. Mine.");
                RefreshAfterChange();
        }
        return Heard;
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
        AdvanceSimDay();
        AddJournalEntry("Day " + std::to_string(VillageSys->Day()) + ". The village wakes to " + std::string(ToString(VillageSys->Weather())) + ".");
        QuestSys->ActivateDue(*this);
        RefreshAfterChange();
        return true;
}

void Game::AdvanceSimDay()
{
        const int NextDay = VillageSys->Day() + 1;
        VillageSys->BeginDay(NextDay);
        // a new day: memory fades, rumors born today enter circulation
        RumorSys->ApplyDailyDecay(NextDay);
        RumorSys->ActivateDue(NextDay);
        // urgent quests whose day window closed fail with story consequences
        for (const std::string& FailedId : QuestSys->ProcessExpiry(*this))
        {
                const QuestDef* Def = QuestSys->FindDef(FailedId);
                if (Def)
                {
                        for (const auto& KV : Def->FlagsOnFail) { FlagValues[KV.first] = KV.second; }
                        AddJournalEntry("Failed: " + Def->Title + " (" + Def->Chapter + ")");
                }
        }
        // quests whose day window opens today enter play
        QuestSys->ActivateDue(*this);
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

bool Game::PlayerHeardRumor(const std::string& RumorId) const
{
        for (const std::string& R : RumorSys->PlayerKnownRumors())
        {
                if (R == RumorId) { return true; }
        }
        return false;
}

// ------------------------------------------------------------ save/load

JsonValue Game::Save() const
{
        JsonValue Root = JsonValue::MakeObject();
        Root.Set("save_version", JsonValue(2));   // v2: rumors + deterministic sim RNG (M2)
        Root.Set("village", VillageSys->SerializeState());
        Root.Set("evidence", EvidenceSys->SerializeState());
        Root.Set("quests", QuestSys->SerializeState());
        Root.Set("rumors", RumorSys->SerializeState());
        // 64-bit RNG state travels as hex text - a double would lose bits above 2^53
        {
                char RngBuf[32];
                std::snprintf(RngBuf, sizeof(RngBuf), "%016llx", static_cast<unsigned long long>(SimRngStream.State64()));
                Root.Set("sim_rng", JsonValue(std::string(RngBuf)));
        }

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

// M3.1: the raw load. Mutates subsystems in sequence - NOT atomic on its own
// (a payload that corrupts a later section would leave earlier sections
// applied). Game::LoadFromString wraps this with a snapshot-rollback guard.
bool Game::LoadFromStringInternal(const std::string& Payload, std::string& OutError)
{
        JsonParseResult P = JsonParse(Payload);
        if (!P.Ok) { OutError = "save payload is not valid JSON: " + P.Error; return false; }
        const JsonValue& Root = P.Value;
        if (!Root.IsObject()) { OutError = "save root not an object"; return false; }

        // ---- version gate: 1 = M1 legacy, 2 = M2 (rumors + sim RNG) ----
        const int SaveVersion = Root.Find("save_version") ? Root.Find("save_version")->AsInt() : 0;
        if (SaveVersion <= 0 || SaveVersion > 2)
        {
                OutError = "unsupported save_version " + std::to_string(SaveVersion)
                        + " (this build reads 1 and 2)";
                return false;
        }

        const JsonValue* V = Root.Find("village");
        if (!V || !VillageSys->DeserializeState(*V, OutError)) { OutError = "village: " + OutError; return false; }
        const JsonValue* E = Root.Find("evidence");
        if (!E || !EvidenceSys->DeserializeState(*E, OutError)) { OutError = "evidence: " + OutError; return false; }
        const JsonValue* Q = Root.Find("quests");
        if (!Q || !QuestSys->DeserializeState(*Q, OutError)) { OutError = "quests: " + OutError; return false; }

        if (SaveVersion >= 2)
        {
                // v2 must carry the rumor layer and the sim RNG - refuse a silent
                // downgrade that would resurrect a contradicting world state.
                const JsonValue* R = Root.Find("rumors");
                if (!R || !RumorSys->DeserializeState(*R, OutError)) { OutError = "rumors: " + OutError; return false; }
                const JsonValue* RNG = Root.Find("sim_rng");
                if (!RNG || !RNG->IsString()) { OutError = "rumors: save v2 missing sim_rng"; return false; }
                SimRngStream.SetState(std::strtoull(RNG->AsString().c_str(), nullptr, 16));
        }
        else
        {
                // legacy v1: no rumor layer in the payload - start it clean rather
                // than resurrect stale knowledge from the current session.
                std::string Ignored;
                JsonValue Empty = JsonValue::MakeObject();
                RumorSys->DeserializeState(Empty, Ignored);
        }

        FlagValues.clear();
        if (const JsonValue* F = Root.Find("flags"))
        {
                if (!F->IsObject()) { OutError = "flags not an object"; return false; }
                for (const auto& KV : F->AsObject())
                {
                        if (!KV.second.IsNumber()) { OutError = "flag value not a number: " + KV.first; return false; }
                        FlagValues[KV.first] = KV.second.AsInt();
                }
        }
        ReachedAreas.clear();
        if (const JsonValue* A = Root.Find("reached_areas"))
        {
                if (!A->IsArray()) { OutError = "reached_areas not an array"; return false; }
                for (size_t I = 0; I < A->Size(); ++I)
                {
                        const JsonValue* Item = A->At(I);
                        if (!Item || !Item->IsString()) { OutError = "reached_areas item not a string"; return false; }
                        ReachedAreas.insert(Item->AsString());
                }
        }
        DialogueHistory.clear();
        if (const JsonValue* H = Root.Find("dialogue_history"))
        {
                if (!H->IsObject()) { OutError = "dialogue_history not an object"; return false; }
                for (const auto& KV : H->AsObject())
                {
                        if (!KV.second.IsArray()) { OutError = "dialogue_history entry not an array"; return false; }
                        std::set<std::string> Nodes;
                        for (size_t I = 0; I < KV.second.Size(); ++I)
                        {
                                const JsonValue* N = KV.second.At(I);
                                if (!N || !N->IsString()) { OutError = "dialogue_history node not a string"; return false; }
                                Nodes.insert(N->AsString());
                        }
                        DialogueHistory[KV.first] = Nodes;
                }
        }
        JournalEntries.clear();
        if (const JsonValue* J = Root.Find("journal"))
        {
                if (!J->IsArray()) { OutError = "journal not an array"; return false; }
                for (size_t I = 0; I < J->Size(); ++I)
                {
                        const JsonValue* Entry = J->At(I);
                        if (!Entry || !Entry->IsObject()) { OutError = "journal entry not an object"; return false; }
                        JournalEntry JE;
                        JE.Day = Entry->GetInt("day", 1);
                        JE.Text = Entry->GetString("text", "");
                        if (JE.Day < 1 || JE.Day > 9) { OutError = "journal entry day out of range"; return false; }
                        JournalEntries.push_back(JE);
                }
        }

        // an interrupted dialogue is not part of a save (save happens at the desk)
        DialogueSys->EndSession();
        return true;
}

// M3.1 atomic load: a refused load must leave the running session exactly as
// it was - no partially-applied village/evidence/quests/rumors mixture. The
// session is snapshotted before the attempt; any rejection rolls it back from
// that snapshot (a payload produced by SaveToString() always reloads cleanly).
bool Game::LoadFromString(const std::string& Payload, std::string& OutError)
{
        const std::string Rollback = SaveToString();
        if (LoadFromStringInternal(Payload, OutError)) { return true; }

        std::string RestoreErr;
        if (!LoadFromStringInternal(Rollback, RestoreErr))
        {
                // unreachable for snapshots produced by SaveToString(); if it ever
                // fires, surface it loudly instead of silently continuing mixed.
                OutError += " (CRITICAL: refused-load rollback failed: " + RestoreErr + ")";
        }
        return false;
}

} // namespace tls
