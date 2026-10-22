// THE LAST SIN: The Sin-Eater - M1
// TLSDialogue: dialogue tree engine - node traversal, tone-tagged choices,
// condition gating (flags/trust/evidence/insights/welsh/day/quests) and
// evidence presentation reactions.
// Semantics per docs/QUEST_ARCHITECTURE.md 5 (Dialogue System) and
// GAME_BIBLE.md 6.2.5 (tones + the Welsh language layer).

#pragma once

#include "TLSCoreTypes.h"
#include "TLSJson.h"

#include <map>
#include <string>
#include <vector>

namespace tls
{

class DialogueSystem
{
public:
        // Loads ONE dialogue definition (a file may contain a single tree).
        bool Load(const JsonValue& Root, std::string& OutError);

        const DialogueDef* FindDef(const std::string& Id) const;
        const std::map<std::string, DialogueDef>& Defs() const { return Dialogues; }

        // ---- condition evaluation (shared with the game state) ----
        static bool EvaluateConditions(const DialogueConditions& C, const IGameContext& Ctx,
                const std::string& NpcId);

        // ---- session ----
        bool Start(const std::string& DialogueId, std::string& OutError);
        void EndSession();
        bool IsActive() const { return !ActiveDialogueId.empty(); }
        const std::string& ActiveDialogue() const { return ActiveDialogueId; }
        const DialogueNode* CurrentNode() const;

        // Choices of the current node that pass their conditions, in file order.
        std::vector<const DialogueChoice*> AvailableChoices(const IGameContext& Ctx) const;

        struct ChoiceResult
        {
                const DialogueChoice* Choice = nullptr;
                std::string NextNodeId;      // empty -> the dialogue ends
        };

        // Picks the Nth AVAILABLE choice (index into AvailableChoices result).
        bool Choose(size_t IndexInAvailable, const IGameContext& Ctx, ChoiceResult& Out, std::string& OutError);

        // For nodes without choices: the auto-continue target ("" = end).
        std::string AutoNext() const;

        // Moves the session to a node (root on Start). Returns the node entered.
        const DialogueNode* EnterNode(const std::string& NodeId);

        // Marks that the running session reached its natural end.
        void MarkEnded() { ActiveDialogueId.clear(); CurrentNodeId.clear(); }

        // Sanity check used by validators/tests: every next/choice target exists.
        bool ValidateGraph(const std::string& DialogueId, std::string& OutError) const;

private:
        std::map<std::string, DialogueDef> Dialogues;
        std::string ActiveDialogueId;
        std::string CurrentNodeId;
};

} // namespace tls
