// THE LAST SIN: The Sin-Eater - M1
// TLSEvidence: evidence inventory, examination table state, the deduction
// board (link rules, contradictions, insights) and chain of custody.
// Semantics per docs/QUEST_ARCHITECTURE.md 2 (Evidence & Deduction).

#pragma once

#include "TLSCoreTypes.h"
#include "TLSJson.h"

#include <map>
#include <set>
#include <string>
#include <vector>

namespace tls
{

struct EvidenceRuntime
{
        bool bObserved = false;
        bool bCollected = false;
        bool bExamined = false;
        bool bRestored = false;    // documentary pages restored with the etching skill
        int DayCollected = 0;
        std::vector<std::string> ChainOfCustody;
};

struct DrawnLink
{
        std::string A;
        std::string B;
        std::string RuleId;             // empty when no rule matched (unknown pair)
        bool bValid = false;
        bool bContradiction = false;
        std::string Note;
        int DayDrawn = 1;
};

class EvidenceSystem
{
public:
        // ---- loading ----
        bool Load(const JsonValue& Root, std::string& OutError);

        // ---- queries (defs) ----
        const EvidenceDef* FindDef(const std::string& Id) const;
        const std::map<std::string, EvidenceDef>& Defs() const { return EvidenceDefs; }
        const InsightDef* FindInsight(const std::string& Id) const;
        const std::map<std::string, InsightDef>& Insights() const { return InsightDefs; }

        // ---- state transitions ----
        bool NotifyObserved(const std::string& Id, int Day, std::string* OutNote = nullptr);
        bool NotifyCollected(const std::string& Id, int Day, const std::string& CustodyEntry);
        bool NotifyExamined(const std::string& Id, int Day, std::string* OutReveal = nullptr);
        bool NotifyRestored(const std::string& Id, int Day, std::string* OutReveal = nullptr);

        // ---- deduction board ----
        enum class ELinkVerdict { NoRule, Supporting, Insight, Contradiction, Already };
        ELinkVerdict DrawLink(const std::string& A, const std::string& B, int Day,
                std::string& OutMessage, std::vector<std::string>& OutNewInsights);

        // ---- queries (state) ----
        const EvidenceRuntime* State(const std::string& Id) const;
        bool IsCollected(const std::string& Id) const;
        bool IsExamined(const std::string& Id) const;
        bool IsObserved(const std::string& Id) const;
        bool IsRestored(const std::string& Id) const;
        bool InsightKnown(const std::string& Id) const;
        const std::vector<DrawnLink>& Links() const { return DrawnLinks; }
        std::vector<std::string> CollectedIds() const;

        // ---- dialogue reactions / direct grants ----
        bool AppendChainNote(const std::string& Id, const std::string& Note); // "denied by ..."
        bool ForceInsight(const std::string& InsightId);                    // rare direct grants

        // ---- save / load ----
        JsonValue SerializeState() const;
        bool DeserializeState(const JsonValue& Root, std::string& OutError);

private:
        void EvaluateInsights(std::vector<std::string>& OutNew);

        std::map<std::string, EvidenceDef> EvidenceDefs;
        std::map<std::string, LinkRule> LinkRules;
        std::map<std::string, InsightDef> InsightDefs;
        std::map<std::string, EvidenceRuntime> Runtime;
        std::vector<DrawnLink> DrawnLinks;
        std::set<std::string> KnownInsights;
        std::set<std::string> GrantedByInsight;   // evidence auto-granted by an insight effect
        std::map<std::string, std::string> InsightGated;  // evidence id -> gating insight id
};

} // namespace tls
