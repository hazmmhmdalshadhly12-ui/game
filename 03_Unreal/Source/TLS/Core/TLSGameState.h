// THE LAST SIN: The Sin-Eater - M1
// TLSGameState: the game orchestrator - owns the four core systems, applies
// dialogue effects, receives world notifications, advances the day script,
// keeps the journal and serializes the whole state for the save system.
// This is the object the UE layer (TLSVillageGameMode) talks to.

#pragma once

#include "TLSCoreTypes.h"
#include "TLSEvidence.h"
#include "TLSQuests.h"
#include "TLSVillageState.h"
#include "TLSDialogue.h"
#include "TLSRumors.h"
#include "TLSSettings.h"
#include "TLSRng.h"

#include <map>
#include <set>
#include <string>
#include <vector>

namespace tls
{

class Game : public IGameContext
{
public:
        Game();
        ~Game() override;

        // ---- data loading (call once, before NewGame) ----
        bool LoadEvidenceData(const JsonValue& Root, std::string& OutError);
        bool LoadQuestData(const JsonValue& Root, std::string& OutError);
        bool LoadSimData(const JsonValue& Root, std::string& OutError);
        bool LoadDialogueData(const JsonValue& Root, std::string& OutError);
        bool LoadRumorData(const JsonValue& Root, std::string& OutError);

        // ---- session ----
        void NewGame();
        // Pure simulation day advance (no story gates): BeginDay + rumor decay
        // + rumor activation. Used by the 7-day sim test and by a headless UE
        // day script; the QUEST layer keeps its own gate in NotifySleep.
        void AdvanceSimDay();
        bool IsValid() const { return bDataLoaded; }

        // ---- subsystem access (read-only for callers) ----
        const EvidenceSystem& Evidence() const { return *EvidenceSys; }
        const QuestSystem& Quests() const { return *QuestSys; }
        const VillageState& Village() const { return *VillageSys; }
        const DialogueSystem& Dialogue() const { return *DialogueSys; }
        const RumorSystem& Rumors() const { return *RumorSys; }
        const SettingsModel& Settings() const { return SettingsCfg; }
        SettingsModel& SettingsMut() { return SettingsCfg; }
        EvidenceSystem& EvidenceMut() { return *EvidenceSys; }
        VillageState& VillageMut() { return *VillageSys; }
        QuestSystem& QuestsMut() { return *QuestSys; }

        // ---- M2.1 rumor / witness driving (UE layer or test harness) ----
        // One hour of village gossip. Deterministic given the sim RNG state.
        RumorSystem::TickResult TickVillageGossip(int Day, int Hour);
        bool NotifyWitnessEvent(const std::string& RumorId, int Day, int Hour, const std::string& Zone,
                const std::vector<std::string>& WitnessNpcIds, std::string& OutError);
        bool NotifyPlayerHeardRumor(const std::string& RumorId, const std::string& FromNpc);
        int NotifyPlayerRumorDenial();
        // Anonymous leak (NPC_SIMULATION 5c): feeds the rumor into a gossip zone.
        // Returns the number of NPCs that heard it, or -1 with OutError set.
        int NotifyPlayerLeakRumor(const std::string& RumorId, const std::string& Zone, std::string& OutError);
        // Deterministic simulation stream for gameplay systems that must roll.
        Rng& SimRng() { return SimRngStream; }
        void SetSimRngState(std::uint64_t S) { SimRngStream.SetState(S); }
        std::uint64_t SimRngState() const { return SimRngStream.State64(); }

        // ---- world notifications (from the UE layer or the test harness) ----
        void NotifyReachArea(const std::string& AreaId);
        void NotifyObserveEvidence(const std::string& Id, std::string* OutNote = nullptr);
        void NotifyCollectEvidence(const std::string& Id, const std::string& HowAcquired);
        void NotifyExamineEvidence(const std::string& Id, std::string* OutReveal = nullptr);
        void NotifyRestorePage(const std::string& Id, std::string* OutReveal = nullptr);
        void NotifyDrawLink(const std::string& A, const std::string& B, std::string* OutMessage = nullptr,
                std::vector<std::string>* OutNewInsights = nullptr);
        void NotifyDecision(const std::string& FlagId, int Value);
        // End of day. Refuses (returns false) when the story gate is not met:
        // day 1 requires Q-M-C1 completed; day 2 is the slice boundary.
        bool NotifySleep(std::string& OutReason);

        // ---- dialogue driving ----
        bool BeginDialogue(const std::string& DialogueId, std::string& OutError);
        // Returns false when the dialogue is not running / index invalid.
        // OutEnteredNodeId receives the node entered after the choice ("" = dialogue ended).
        bool PickDialogueChoice(size_t IndexInAvailable, std::string& OutEnteredNodeId, std::string& OutError);
        // For nodes without choices: applies OnEnter of the target node and advances.
        bool DialogueAutoAdvance(std::string& OutEnteredNodeId);
        bool DialogueRunning() const;
        const DialogueNode* DialogueCurrentNode() const;
        std::vector<const DialogueChoice*> DialogueAvailableChoices() const;
        // Rendered text (Welsh layer applied) for the current node.
        std::string DialogueRenderedText(bool& OutNeedsLesson) const;

        // ---- IGameContext ----
        int CurrentDay() const override { return VillageSys->Day(); }
        ETimeOfDay GetTimeOfDay() const override { return VillageSys->TimeOfDay(); }
        EWeather GetWeather() const override { return VillageSys->Weather(); }
        bool HasReachedArea(const std::string& AreaId) const override { return ReachedAreas.count(AreaId) != 0; }
        bool EvidenceObserved(const std::string& Id) const override { return EvidenceSys->IsObserved(Id); }
        bool EvidenceCollected(const std::string& Id) const override { return EvidenceSys->IsCollected(Id); }
        bool EvidenceExamined(const std::string& Id) const override { return EvidenceSys->IsExamined(Id); }
        bool EvidenceRestored(const std::string& Id) const override { return EvidenceSys->IsRestored(Id); }
        bool InsightKnown(const std::string& Id) const override { return EvidenceSys->InsightKnown(Id); }
        bool DialogueNodeSeen(const std::string& DialogueId, const std::string& NodeId) const override;
        int GetFlag(const std::string& FlagId) const override;
        bool IsQuestCompleted(const std::string& QuestId) const override { return QuestSys->Status(QuestId) == EQuestStatus::Completed; }
        double GetTrust(const std::string& NpcId) const override { return VillageSys->GetTrust(NpcId); }
        int GetWelshLevel() const override { return GetFlag("FLG_EDMUND_WELSH_LEVEL"); }
        bool NpcKnowsRumor(const std::string& NpcId, const std::string& RumorId) const override { return RumorSys->NpcKnows(NpcId, RumorId); }
        bool PlayerHeardRumor(const std::string& RumorId) const override;
        double GetTension() const override { return VillageSys->Tension(); }

        // ---- journal ----
        struct JournalEntry
        {
                int Day = 1;
                std::string Text;
        };
        const std::vector<JournalEntry>& Journal() const { return JournalEntries; }
        void AddJournalEntry(const std::string& Text);

        // ---- save / load ----
        JsonValue Save() const;
        std::string SaveToString() const;                       // compact JSON payload
        bool LoadFromString(const std::string& Payload, std::string& OutError);

        // flags map (read access for UI/tests)
        const std::map<std::string, int>& Flags() const { return FlagValues; }

private:
        void ApplyEffects(const DialogueEffects& Effects, const std::string& NpcId, ETone Tone);
        void ApplyQuestCompletionFlags(const std::vector<std::string>& CompletedQuestIds);
        void RefreshAfterChange();
        void EnterNodeAndApply(const std::string& NodeId, std::string& OutEnteredNodeId);

        EvidenceSystem* EvidenceSys = nullptr;
        QuestSystem* QuestSys = nullptr;
        VillageState* VillageSys = nullptr;
        DialogueSystem* DialogueSys = nullptr;
        RumorSystem* RumorSys = nullptr;
        SettingsModel SettingsCfg;
        Rng SimRngStream;

        bool bDataLoaded = false;
        std::map<std::string, int> FlagValues;
        std::set<std::string> ReachedAreas;
        std::map<std::string, std::set<std::string>> DialogueHistory;  // dlg id -> seen nodes
        std::vector<JournalEntry> JournalEntries;
};

} // namespace tls
