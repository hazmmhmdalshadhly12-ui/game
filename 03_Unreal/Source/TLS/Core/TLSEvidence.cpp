// THE LAST SIN: The Sin-Eater - M1
// TLSEvidence.cpp

#include "TLSEvidence.h"

namespace tls
{

bool EvidenceSystem::Load(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "evidence root must be an object"; return false; }

        // 1) evidence definitions --------------------------------------
        const JsonValue* Evidence = Root.Find("evidence");
        if (!Evidence || !Evidence->IsArray()) { OutError = "missing 'evidence' array"; return false; }
        for (size_t I = 0; I < Evidence->Size(); ++I)
        {
                const JsonValue* E = Evidence->At(I);
                if (!E || !E->IsObject()) { OutError = "evidence entry not an object"; return false; }
                EvidenceDef Def;
                Def.Id = E->GetString("id", "");
                Def.Name = E->GetString("name", "");
                Def.Description = E->GetString("description", "");
                Def.ExamineDetail = E->GetString("examine_detail", "");
                Def.Source = E->GetString("source", "");
                Def.DayAcquired = E->GetInt("day_acquired", 1);
                if (Def.Id.empty()) { OutError = "evidence entry missing id"; return false; }
                std::string TypeStr = E->GetString("type", "physical");
                if (!ParseEvidenceType(TypeStr, Def.Type)) { OutError = "bad evidence type '" + TypeStr + "' on " + Def.Id; return false; }
                Def.Reliability = E->GetNumber("reliability", 0.5);
                if (Def.Reliability < 0.0 || Def.Reliability > 1.0) { OutError = "reliability out of range on " + Def.Id; return false; }
                Def.bRestorable = E->GetBool("restorable", false);
                EvidenceDefs[Def.Id] = Def;
        }

        // 2) link rules (cross-refs to insights validated in step 4) ---
        const JsonValue* Rules = Root.Find("link_rules");
        if (!Rules || !Rules->IsArray()) { OutError = "missing 'link_rules' array"; return false; }
        for (size_t I = 0; I < Rules->Size(); ++I)
        {
                const JsonValue* R = Rules->At(I);
                if (!R || !R->IsObject()) { OutError = "link rule not an object"; return false; }
                LinkRule Rule;
                Rule.Id = R->GetString("id", "");
                Rule.A = R->GetString("a", "");
                Rule.B = R->GetString("b", "");
                Rule.bValid = R->GetBool("valid", true);
                Rule.InsightId = R->GetString("insight", "");
                Rule.Note = R->GetString("note", "");
                Rule.ContradictionReason = R->GetString("contradiction_reason", "");
                if (Rule.Id.empty() || Rule.A.empty() || Rule.B.empty()) { OutError = "link rule missing id/a/b"; return false; }
                if (!EvidenceDefs.count(Rule.A)) { OutError = "link rule " + Rule.Id + " references unknown evidence " + Rule.A; return false; }
                if (!EvidenceDefs.count(Rule.B)) { OutError = "link rule " + Rule.Id + " references unknown evidence " + Rule.B; return false; }
                if (!Rule.bValid && Rule.ContradictionReason.empty()) { OutError = "invalid rule " + Rule.Id + " needs contradiction_reason"; return false; }
                LinkRules[Rule.Id] = Rule;
        }

        // 3) insights (cross-refs to rules validated in step 4) --------
        const JsonValue* Insights = Root.Find("insights");
        if (!Insights || !Insights->IsArray()) { OutError = "missing 'insights' array"; return false; }
        for (size_t I = 0; I < Insights->Size(); ++I)
        {
                const JsonValue* In = Insights->At(I);
                if (!In || !In->IsObject()) { OutError = "insight not an object"; return false; }
                InsightDef Def;
                Def.Id = In->GetString("id", "");
                Def.Name = In->GetString("name", "");
                Def.Description = In->GetString("description", "");
                if (Def.Id.empty()) { OutError = "insight missing id"; return false; }
                if (const JsonValue* Paths = In->Find("link_paths"))
                {
                        for (size_t P = 0; P < Paths->Size(); ++P)
                        {
                                const JsonValue* Path = Paths->At(P);
                                if (!Path || !Path->IsArray()) { OutError = "insight " + Def.Id + " has a malformed link path"; return false; }
                                std::vector<std::string> PathIds;
                                for (size_t K = 0; K < Path->Size(); ++K)
                                {
                                        const JsonValue* L = Path->At(K);
                                        if (!L || !L->IsString()) { OutError = "insight " + Def.Id + " path item not a string"; return false; }
                                        PathIds.push_back(L->AsString());
                                }
                                if (PathIds.empty()) { OutError = "insight " + Def.Id + " has an empty link path"; return false; }
                                Def.LinkPaths.push_back(PathIds);
                        }
                }
                Def.RequiresExamined = In->GetStringList("requires_examined");
                for (const std::string& Ev : Def.RequiresExamined)
                {
                        if (!EvidenceDefs.count(Ev)) { OutError = "insight " + Def.Id + " requires unknown evidence " + Ev; return false; }
                }
                if (Def.LinkPaths.empty()) { OutError = "insight " + Def.Id + " has no link paths"; return false; }
                InsightDefs[Def.Id] = Def;
        }

        // 4) cross-reference validation --------------------------------
        for (const auto& KV : LinkRules)
        {
                if (!KV.second.InsightId.empty() && !InsightDefs.count(KV.second.InsightId))
                {
                        OutError = "link rule " + KV.first + " references unknown insight " + KV.second.InsightId;
                        return false;
                }
        }
        for (const auto& KV : InsightDefs)
        {
                for (const std::vector<std::string>& Path : KV.second.LinkPaths)
                {
                        for (const std::string& LinkId : Path)
                        {
                                if (!LinkRules.count(LinkId)) { OutError = "insight " + KV.first + " references unknown link " + LinkId; return false; }
                        }
                }
        }

        // 5) insight-gated documentary evidence ------------------------
        for (const auto& KV : EvidenceDefs)
        {
                if (KV.second.Type == EEvidenceType::Documentary && !KV.second.Source.empty()
                        && KV.second.Source.rfind("insight:", 0) == 0)
                {
                        const std::string InsightId = KV.second.Source.substr(8);
                        if (!InsightDefs.count(InsightId)) { OutError = "evidence " + KV.first + " gated by unknown insight " + InsightId; return false; }
                        InsightGated[KV.first] = InsightId;
                }
        }

        return true;
}

const EvidenceDef* EvidenceSystem::FindDef(const std::string& Id) const
{
        auto It = EvidenceDefs.find(Id);
        return It == EvidenceDefs.end() ? nullptr : &It->second;
}

const InsightDef* EvidenceSystem::FindInsight(const std::string& Id) const
{
        auto It = InsightDefs.find(Id);
        return It == InsightDefs.end() ? nullptr : &It->second;
}

bool EvidenceSystem::NotifyObserved(const std::string& Id, int Day, std::string* OutNote)
{
        auto It = EvidenceDefs.find(Id);
        if (It == EvidenceDefs.end()) { return false; }
        EvidenceRuntime& R = Runtime[Id];
        if (!R.bObserved)
        {
                R.bObserved = true;
                R.ChainOfCustody.push_back("day " + std::to_string(Day) + ": observed in the world");
                if (OutNote) { *OutNote = It->second.Description; }
        }
        else if (OutNote) { *OutNote = It->second.Description; }
        return true;
}

bool EvidenceSystem::NotifyCollected(const std::string& Id, int Day, const std::string& CustodyEntry)
{
        auto It = EvidenceDefs.find(Id);
        if (It == EvidenceDefs.end()) { return false; }
        EvidenceRuntime& R = Runtime[Id];
        if (R.bCollected) { return true; }
        R.bCollected = true;
        R.bObserved = true;
        R.DayCollected = Day;
        R.ChainOfCustody.push_back("day " + std::to_string(Day) + ": " + CustodyEntry);
        return true;
}

bool EvidenceSystem::NotifyExamined(const std::string& Id, int Day, std::string* OutReveal)
{
        auto It = EvidenceDefs.find(Id);
        if (It == EvidenceDefs.end()) { return false; }
        EvidenceRuntime& R = Runtime[Id];
        if (!R.bCollected) { return false; }   // must be in the satchel first
        if (!R.bExamined)
        {
                R.bExamined = true;
                R.ChainOfCustody.push_back("day " + std::to_string(Day) + ": examined on the father's table");
        }
        if (OutReveal)
        {
                // a restorable page shows its full text only after the etching repair
                if (It->second.bRestorable && !R.bRestored)
                {
                        *OutReveal = "The tear runs through the entries. Charcoal and a flat weight will raise the rest.";
                }
                else
                {
                        *OutReveal = It->second.ExamineDetail;
                }
        }
        return true;
}

bool EvidenceSystem::NotifyRestored(const std::string& Id, int Day, std::string* OutReveal)
{
        auto It = EvidenceDefs.find(Id);
        if (It == EvidenceDefs.end()) { return false; }
        if (!It->second.bRestorable) { return false; }
        EvidenceRuntime& R = Runtime[Id];
        if (!R.bCollected) { return false; }
        if (!R.bRestored)
        {
                R.bRestored = true;
                R.ChainOfCustody.push_back("day " + std::to_string(Day) + ": page restored (charcoal and etching)");
        }
        if (OutReveal) { *OutReveal = It->second.ExamineDetail; }
        return true;
}

EvidenceSystem::ELinkVerdict EvidenceSystem::DrawLink(const std::string& A, const std::string& B, int Day,
        std::string& OutMessage, std::vector<std::string>& OutNewInsights)
{
        if (!EvidenceDefs.count(A) || !EvidenceDefs.count(B)) { OutMessage = "unknown evidence"; return ELinkVerdict::NoRule; }
        if (A == B) { OutMessage = "a page cannot testify against itself"; return ELinkVerdict::NoRule; }

        // The board takes only what the lamp has read: both pages must be examined.
        if (!IsExamined(A) || !IsExamined(B))
        {
                OutMessage = "The board takes only what the lamp has read - examine both pages on the table first.";
                return ELinkVerdict::NoRule;
        }

        for (const DrawnLink& L : DrawnLinks)
        {
                if ((L.A == A && L.B == B) || (L.A == B && L.B == A))
                {
                        OutMessage = "already drawn";
                        return ELinkVerdict::Already;
                }
        }

        const std::string First = A < B ? A : B;
        const std::string Second = A < B ? B : A;

        const LinkRule* Matched = nullptr;
        for (const auto& KV : LinkRules)
        {
                const LinkRule& R = KV.second;
                if ((R.A == First && R.B == Second) || (R.A == Second && R.B == First)) { Matched = &R; break; }
        }

        DrawnLink L;
        L.A = First;
        L.B = Second;
        L.DayDrawn = Day;
        if (!Matched)
        {
                L.bValid = false;
                L.Note = "No established connection. The ledger keeps its silence.";
                DrawnLinks.push_back(L);
                OutMessage = L.Note;
                return ELinkVerdict::NoRule;
        }
        L.RuleId = Matched->Id;
        L.bValid = Matched->bValid;
        if (!Matched->bValid)
        {
                L.bContradiction = true;
                L.Note = Matched->ContradictionReason;
                DrawnLinks.push_back(L);
                OutMessage = "CONTRADICTION - " + L.Note;
                return ELinkVerdict::Contradiction;
        }
        L.Note = Matched->Note;
        DrawnLinks.push_back(L);

        EvaluateInsights(OutNewInsights);

        if (Matched->InsightId.empty())
        {
                OutMessage = "Consistent - " + L.Note;
                return ELinkVerdict::Supporting;
        }
        OutMessage = "Link holds - " + L.Note;
        return ELinkVerdict::Insight;
}

void EvidenceSystem::EvaluateInsights(std::vector<std::string>& OutNew)
{
        for (const auto& KV : InsightDefs)
        {
                const InsightDef& Def = KV.second;
                if (KnownInsights.count(Def.Id)) { continue; }

                bool bPathDone = false;
                for (const std::vector<std::string>& Path : Def.LinkPaths)
                {
                        bool bAll = true;
                        for (const std::string& LinkId : Path)
                        {
                                bool bFound = false;
                                for (const DrawnLink& L : DrawnLinks)
                                {
                                        if (L.RuleId == LinkId && L.bValid) { bFound = true; break; }
                                }
                                if (!bFound) { bAll = false; break; }
                        }
                        if (bAll) { bPathDone = true; break; }
                }

                bool bExamined = true;
                for (const std::string& Ev : Def.RequiresExamined)
                {
                        const EvidenceRuntime* R = State(Ev);
                        if (!R || !R->bExamined) { bExamined = false; break; }
                }

                if (bPathDone && bExamined)
                {
                        KnownInsights.insert(Def.Id);
                        OutNew.push_back(Def.Id);
                }
        }

        // insight-gated documentary evidence becomes part of the file
        for (const auto& KV : InsightGated)
        {
                if (KnownInsights.count(KV.second) && !Runtime[KV.first].bCollected)
                {
                        EvidenceRuntime& R = Runtime[KV.first];
                        R.bCollected = true;
                        R.bObserved = true;
                        R.DayCollected = 0; // derived, not found on a day
                        R.ChainOfCustody.push_back("derived from insight " + KV.second);
                        GrantedByInsight.insert(KV.first);
                }
        }
}

const EvidenceRuntime* EvidenceSystem::State(const std::string& Id) const
{
        auto It = Runtime.find(Id);
        return It == Runtime.end() ? nullptr : &It->second;
}

bool EvidenceSystem::IsCollected(const std::string& Id) const
{
        const EvidenceRuntime* R = State(Id);
        return R && R->bCollected;
}

bool EvidenceSystem::IsExamined(const std::string& Id) const
{
        const EvidenceRuntime* R = State(Id);
        return R && R->bExamined;
}

bool EvidenceSystem::IsObserved(const std::string& Id) const
{
        const EvidenceRuntime* R = State(Id);
        return R && R->bObserved;
}

bool EvidenceSystem::IsRestored(const std::string& Id) const
{
        const EvidenceRuntime* R = State(Id);
        return R && R->bRestored;
}

bool EvidenceSystem::InsightKnown(const std::string& Id) const
{
        return KnownInsights.count(Id) != 0;
}

bool EvidenceSystem::AppendChainNote(const std::string& Id, const std::string& Note)
{
        auto It = Runtime.find(Id);
        if (It == Runtime.end()) { return false; }
        It->second.ChainOfCustody.push_back(Note);
        return true;
}

bool EvidenceSystem::ForceInsight(const std::string& InsightId)
{
        if (!InsightDefs.count(InsightId)) { return false; }
        if (KnownInsights.count(InsightId)) { return true; }
        KnownInsights.insert(InsightId);
        // re-derive insight-gated grants
        std::vector<std::string> Ignored;
        EvaluateInsights(Ignored);
        return true;
}

std::vector<std::string> EvidenceSystem::CollectedIds() const
{
        std::vector<std::string> Out;
        for (const auto& KV : Runtime)
        {
                if (KV.second.bCollected) { Out.push_back(KV.first); }
        }
        return Out;
}

JsonValue EvidenceSystem::SerializeState() const
{
        JsonValue Root = JsonValue::MakeObject();

        JsonValue Ev = JsonValue::MakeArray();
        for (const auto& KV : Runtime)
        {
                JsonValue E = JsonValue::MakeObject();
                E.Set("id", JsonValue(KV.first));
                E.Set("observed", JsonValue(KV.second.bObserved));
                E.Set("collected", JsonValue(KV.second.bCollected));
                E.Set("examined", JsonValue(KV.second.bExamined));
                E.Set("restored", JsonValue(KV.second.bRestored));
                E.Set("day_collected", JsonValue(KV.second.DayCollected));
                JsonValue Chain = JsonValue::MakeArray();
                for (const std::string& C : KV.second.ChainOfCustody) { Chain.Append(JsonValue(C)); }
                E.Set("chain", std::move(Chain));
                Ev.Append(std::move(E));
        }
        Root.Set("evidence", std::move(Ev));

        JsonValue Links = JsonValue::MakeArray();
        for (const DrawnLink& L : DrawnLinks)
        {
                JsonValue J = JsonValue::MakeObject();
                J.Set("a", JsonValue(L.A));
                J.Set("b", JsonValue(L.B));
                J.Set("rule", JsonValue(L.RuleId));
                J.Set("valid", JsonValue(L.bValid));
                J.Set("day", JsonValue(L.DayDrawn));
                Links.Append(std::move(J));
        }
        Root.Set("links", std::move(Links));

        JsonValue Known = JsonValue::MakeArray();
        for (const std::string& K : KnownInsights) { Known.Append(JsonValue(K)); }
        Root.Set("insights_known", std::move(Known));

        return Root;
}

bool EvidenceSystem::DeserializeState(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "evidence state root not an object"; return false; }
        Runtime.clear();
        DrawnLinks.clear();
        KnownInsights.clear();
        GrantedByInsight.clear();

        if (const JsonValue* Ev = Root.Find("evidence"))
        {
                for (size_t I = 0; I < Ev->Size(); ++I)
                {
                        const JsonValue* E = Ev->At(I);
                        if (!E) { continue; }
                        const std::string Id = E->GetString("id", "");
                        // M3.2: the load contract is strict, like village and rumors -
                        // a payload may only reference evidence this build defines.
                        // (Ghost runtime entries would lie to the query API and skew
                        // CollectedIds() counts; legit saves never carry them.)
                        if (Id.empty() || !EvidenceDefs.count(Id))
                        {
                                OutError = "evidence state references unknown evidence \"" + Id + "\"";
                                return false;
                        }
                        EvidenceRuntime R;
                        R.bObserved = E->GetBool("observed", false);
                        R.bCollected = E->GetBool("collected", false);
                        R.bExamined = E->GetBool("examined", false);
                        R.bRestored = E->GetBool("restored", false);
                        R.DayCollected = E->GetInt("day_collected", 0);
                        if (const JsonValue* Chain = E->Find("chain"))
                        {
                                for (size_t K = 0; K < Chain->Size(); ++K)
                                {
                                        const JsonValue* C = Chain->At(K);
                                        if (!C || !C->IsString()) { OutError = "custody chain entry not a string"; return false; }
                                        R.ChainOfCustody.push_back(C->AsString());
                                }
                        }
                        Runtime[Id] = R;
                }
        }
        if (const JsonValue* Links = Root.Find("links"))
        {
                for (size_t I = 0; I < Links->Size(); ++I)
                {
                        const JsonValue* J = Links->At(I);
                        if (!J) { continue; }
                        DrawnLink L;
                        L.A = J->GetString("a", "");
                        L.B = J->GetString("b", "");
                        L.RuleId = J->GetString("rule", "");
                        L.bValid = J->GetBool("valid", false);
                        L.DayDrawn = J->GetInt("day", 1);
                        // M3.2: an empty rule id is the recorded NoRule verdict - kept.
                        // A NAMED rule must exist, or the payload is from another world.
                        if (!L.RuleId.empty() && !LinkRules.count(L.RuleId))
                        {
                                OutError = "link references unknown rule \"" + L.RuleId + "\"";
                                return false;
                        }
                        const LinkRule* Rule = nullptr;
                        auto RuleIt = LinkRules.find(L.RuleId);
                        if (RuleIt != LinkRules.end()) { Rule = &RuleIt->second; }
                        L.bContradiction = Rule && !Rule->bValid;
                        if (Rule) { L.Note = Rule->bValid ? Rule->Note : Rule->ContradictionReason; }
                        DrawnLinks.push_back(L);
                }
        }
        if (const JsonValue* Known = Root.Find("insights_known"))
        {
                for (size_t I = 0; I < Known->Size(); ++I)
                {
                        const JsonValue* K = Known->At(I);
                        if (!K) { continue; }
                        // M3.2: only insights this build defines may load.
                        if (!InsightDefs.count(K->AsString()))
                        {
                                OutError = "insights_known references unknown insight \"" + K->AsString() + "\"";
                                return false;
                        }
                        KnownInsights.insert(K->AsString());
                }
        }
        // re-derive insight-gated evidence grants
        for (const auto& KV : InsightGated)
        {
                if (KnownInsights.count(KV.second) && Runtime[KV.first].bCollected)
                {
                        GrantedByInsight.insert(KV.first);
                }
        }
        return true;
}

} // namespace tls
