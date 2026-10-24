// THE LAST SIN: The Sin-Eater - M3.7
// TLSCaseFacts.cpp

#include "TLSCaseFacts.h"

namespace tls
{

// ------------------------------------------------------------ enum glue

const char* ToString(ETestimonyStance S)
{
        switch (S)
        {
                case ETestimonyStance::Affirms: return "affirms";
                case ETestimonyStance::Denies:  return "denies";
                case ETestimonyStance::Claims:  return "claims";
                case ETestimonyStance::Omits:   return "omits";
        }
        return "affirms";
}

bool ParseTestimonyStance(const std::string& S, ETestimonyStance& Out)
{
        if (S == "affirms") { Out = ETestimonyStance::Affirms; return true; }
        if (S == "denies")  { Out = ETestimonyStance::Denies;  return true; }
        if (S == "claims")  { Out = ETestimonyStance::Claims;  return true; }
        if (S == "omits")   { Out = ETestimonyStance::Omits;   return true; }
        return false;
}

const char* ToString(ETestimonyOrigin O)
{
        switch (O)
        {
                case ETestimonyOrigin::Witnessed:  return "witnessed";
                case ETestimonyOrigin::Told:       return "told";
                case ETestimonyOrigin::Inferred:   return "inferred";
                case ETestimonyOrigin::Documented: return "documented";
        }
        return "witnessed";
}

bool ParseTestimonyOrigin(const std::string& S, ETestimonyOrigin& Out)
{
        if (S == "witnessed")  { Out = ETestimonyOrigin::Witnessed;  return true; }
        if (S == "told")       { Out = ETestimonyOrigin::Told;       return true; }
        if (S == "inferred")   { Out = ETestimonyOrigin::Inferred;   return true; }
        if (S == "documented") { Out = ETestimonyOrigin::Documented; return true; }
        return false;
}

// ------------------------------------------------------------ load

bool CaseFactSystem::Load(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "case facts root must be an object"; return false; }

        const JsonValue* Facts = Root.Find("facts");
        if (!Facts || !Facts->IsArray()) { OutError = "missing 'facts' array"; return false; }
        for (size_t I = 0; I < Facts->Size(); ++I)
        {
                const JsonValue* F = Facts->At(I);
                if (!F || !F->IsObject()) { OutError = "fact entry not an object"; return false; }
                CaseFactDef Def;
                Def.Id = F->GetString("id", "");
                if (Def.Id.empty()) { OutError = "fact entry missing id"; return false; }
                if (FactDefs.count(Def.Id)) { OutError = "duplicate fact id " + Def.Id; return false; }
                Def.Topic = F->GetString("topic", "");
                Def.TruthSummary = F->GetString("truth_summary", "");
                Def.CanonRef = F->GetString("canon_ref", "");
                if (Def.TruthSummary.empty()) { OutError = "fact " + Def.Id + " missing truth_summary"; return false; }
                if (Def.CanonRef.empty()) { OutError = "fact " + Def.Id + " missing canon_ref (no fact without a canon anchor)"; return false; }
                Def.bTruthAnchor = F->GetBool("truth_anchor", false);
                Def.RelatedEvidence = F->GetStringList("related_evidence");
                Def.JournalNote = F->GetString("journal_note", "");
                if (const JsonValue* Flags = F->Find("on_learned_flags"))
                {
                        if (!Flags->IsObject()) { OutError = "fact " + Def.Id + " on_learned_flags not an object"; return false; }
                        for (const auto& KV : Flags->AsObject())
                        {
                                if (!KV.second.IsNumber()) { OutError = "fact " + Def.Id + " flag value not a number: " + KV.first; return false; }
                                Def.OnLearnedFlags[KV.first] = KV.second.AsInt();
                        }
                }

                const JsonValue* Testimonies = F->Find("testimonies");
                if (Testimonies)
                {
                        if (!Testimonies->IsArray()) { OutError = "fact " + Def.Id + " testimonies not an array"; return false; }
                        for (size_t T = 0; T < Testimonies->Size(); ++T)
                        {
                                const JsonValue* TV = Testimonies->At(T);
                                if (!TV || !TV->IsObject()) { OutError = "fact " + Def.Id + " testimony not an object"; return false; }
                                TestimonyDef Test;
                                Test.NpcId = TV->GetString("npc", "");
                                if (Test.NpcId.empty()) { OutError = "fact " + Def.Id + " testimony missing npc"; return false; }
                                for (const TestimonyDef& Existing : Def.Testimonies)
                                {
                                        if (Existing.NpcId == Test.NpcId) { OutError = "fact " + Def.Id + " duplicate testimony for " + Test.NpcId; return false; }
                                }
                                std::string StanceStr = TV->GetString("stance", "affirms");
                                if (!ParseTestimonyStance(StanceStr, Test.Stance)) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " bad stance '" + StanceStr + "'"; return false; }
                                Test.Account = TV->GetString("account", "");
                                Test.ClaimText = TV->GetString("claim_text", "");
                                if (Test.Account.empty() && Test.Stance != ETestimonyStance::Omits) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " missing account"; return false; }
                                if (Test.Stance == ETestimonyStance::Claims && Test.ClaimText.empty()) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " claims without claim_text"; return false; }
                                std::string OriginStr = TV->GetString("origin", "witnessed");
                                if (!ParseTestimonyOrigin(OriginStr, Test.Origin)) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " bad origin '" + OriginStr + "'"; return false; }
                                Test.OriginSource = TV->GetString("origin_source", "");
                                if (Test.Origin == ETestimonyOrigin::Told && Test.OriginSource.empty()) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " told without origin_source"; return false; }
                                Test.Reliability = TV->GetNumber("reliability", 0.5);
                                if (Test.Reliability < 0.0 || Test.Reliability > 1.0) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " reliability out of range"; return false; }
                                Test.bDeliberate = TV->GetBool("deliberate", false);
                                Test.LieReason = TV->GetString("lie_reason", "");
                                if (Test.bDeliberate && Test.LieReason.empty()) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " deliberate without lie_reason (every lie carries a narrative reason)"; return false; }
                                if (!Test.bDeliberate && !Test.LieReason.empty()) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " lie_reason without deliberate"; return false; }
                                Test.bGrantsFact = TV->GetBool("grants", true);
                                if (Test.Stance == ETestimonyStance::Omits && Test.bGrantsFact)
                                {
                                        OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " omits but grants the fact (a silence teaches nothing)";
                                        return false;
                                }

                                if (const JsonValue* Rev = TV->Find("reveal"))
                                {
                                        if (!Rev->IsObject()) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " reveal not an object"; return false; }
                                        Test.Reveal.TrustMin = Rev->GetNumber("trust_min", -100.0);
                                        if (Test.Reveal.TrustMin < -100.0 || Test.Reveal.TrustMin > 100.0) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " trust_min out of range"; return false; }
                                        Test.Reveal.RequiresEvidence = Rev->GetStringList("requires_evidence");
                                        Test.Reveal.RequiresInsights = Rev->GetStringList("requires_insights");
                                        if (const JsonValue* RF = Rev->Find("requires_flags"))
                                        {
                                                if (!RF->IsObject()) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " requires_flags not an object"; return false; }
                                                for (const auto& KV : RF->AsObject())
                                                {
                                                        if (!KV.second.IsNumber()) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " requires_flags value not a number"; return false; }
                                                        Test.Reveal.RequiresFlags[KV.first] = KV.second.AsInt();
                                                }
                                        }
                                        Test.Reveal.DayMin = Rev->GetInt("day_min", 1);
                                        if (Test.Reveal.DayMin < 1) { OutError = "fact " + Def.Id + " testimony " + Test.NpcId + " day_min < 1"; return false; }
                                }
                                Def.Testimonies.push_back(Test);
                        }
                }
                FactDefs[Def.Id] = Def;
        }

        // truth-anchor consistency: an anchor fact must have NO granting testimony
        for (const auto& KV : FactDefs)
        {
                if (!KV.second.bTruthAnchor) { continue; }
                for (const TestimonyDef& T : KV.second.Testimonies)
                {
                        if (T.bGrantsFact)
                        {
                                OutError = "fact " + KV.first + " is a truth anchor but " + T.NpcId + " grants it";
                                return false;
                        }
                }
        }

        const JsonValue* Dossiers = Root.Find("dossiers");
        if (Dossiers)
        {
                if (!Dossiers->IsArray()) { OutError = "'dossiers' not an array"; return false; }
                for (size_t I = 0; I < Dossiers->Size(); ++I)
                {
                        const JsonValue* D = Dossiers->At(I);
                        if (!D || !D->IsObject()) { OutError = "dossier entry not an object"; return false; }
                        DossierDef Def;
                        Def.NpcId = D->GetString("npc", "");
                        if (Def.NpcId.empty()) { OutError = "dossier entry missing npc"; return false; }
                        if (DossierDefs.count(Def.NpcId)) { OutError = "duplicate dossier for " + Def.NpcId; return false; }
                        Def.PublicMotive = D->GetString("public_motive", "");
                        Def.DeepMotive = D->GetString("deep_motive", "");
                        Def.Fear = D->GetString("fear", "");
                        Def.SecretFacts = D->GetStringList("secret_facts");
                        Def.RelationshipNotes = D->GetStringList("relationship_notes");
                        // concealment must be playable: a dossier secret requires a
                        // testimony by THIS npc of THAT fact with a real reveal gate
                        for (const std::string& Secret : Def.SecretFacts)
                        {
                                const CaseFactDef* Fact = FindFact(Secret);
                                if (!Fact) { OutError = "dossier " + Def.NpcId + " secret fact not found: " + Secret; return false; }
                                bool bHasTestimony = false;
                                for (const TestimonyDef& T : Fact->Testimonies)
                                {
                                        if (T.NpcId == Def.NpcId)
                                        {
                                                bHasTestimony = true;
                                                const bool bGated = T.Reveal.TrustMin > -100.0 || !T.Reveal.RequiresEvidence.empty()
                                                        || !T.Reveal.RequiresInsights.empty() || !T.Reveal.RequiresFlags.empty() || T.Reveal.DayMin > 1;
                                                if (!bGated) { OutError = "dossier " + Def.NpcId + " secret " + Secret + " testimony has no reveal gate"; return false; }
                                        }
                                }
                                if (!bHasTestimony) { OutError = "dossier " + Def.NpcId + " secret " + Secret + " has no testimony by this npc"; return false; }
                        }
                        DossierDefs[Def.NpcId] = Def;
                    }
        }

        return true;
}

// ------------------------------------------------------------ queries

const CaseFactDef* CaseFactSystem::FindFact(const std::string& Id) const
{
        auto It = FactDefs.find(Id);
        return It == FactDefs.end() ? nullptr : &It->second;
}

const DossierDef* CaseFactSystem::FindDossier(const std::string& NpcId) const
{
        auto It = DossierDefs.find(NpcId);
        return It == DossierDefs.end() ? nullptr : &It->second;
}

const TestimonyDef* CaseFactSystem::FindTestimony(const std::string& FactId, const std::string& NpcId) const
{
        const CaseFactDef* Fact = FindFact(FactId);
        if (!Fact) { return nullptr; }
        for (const TestimonyDef& T : Fact->Testimonies)
        {
                if (T.NpcId == NpcId) { return &T; }
        }
        return nullptr;
}

bool CaseFactSystem::EvaluateReveal(const RevealConditions& R, const std::string& NpcId, const IGameContext& Ctx) const
{
        if (Ctx.CurrentDay() < R.DayMin) { return false; }
        if (Ctx.GetTrust(NpcId) < R.TrustMin) { return false; }
        for (const std::string& Ev : R.RequiresEvidence)
        {
                if (!Ctx.EvidenceCollected(Ev)) { return false; }
        }
        for (const std::string& In : R.RequiresInsights)
        {
                if (!Ctx.InsightKnown(In)) { return false; }
        }
        for (const auto& KV : R.RequiresFlags)
        {
                if (Ctx.GetFlag(KV.first) != KV.second) { return false; }
        }
        return true;
}

const TestimonyDef* CaseFactSystem::GetAvailableTestimony(const std::string& FactId, const std::string& NpcId,
        const IGameContext& Ctx) const
{
        const TestimonyDef* T = FindTestimony(FactId, NpcId);
        if (!T) { return nullptr; }
        if (!EvaluateReveal(T->Reveal, NpcId, Ctx)) { return nullptr; }
        return T;
}

std::vector<CaseFactSystem::FactConflict> CaseFactSystem::FindConflicts(const std::string& FactId,
        const IGameContext& Ctx) const
{
        std::vector<FactConflict> Out;
        const CaseFactDef* Fact = FindFact(FactId);
        if (!Fact) { return Out; }
        for (size_t A = 0; A < Fact->Testimonies.size(); ++A)
        {
                for (size_t B = A + 1; B < Fact->Testimonies.size(); ++B)
                {
                        const TestimonyDef& TA = Fact->Testimonies[A];
                        const TestimonyDef& TB = Fact->Testimonies[B];
                        // only accounts the player could actually be holding
                        if (!EvaluateReveal(TA.Reveal, TA.NpcId, Ctx) || !EvaluateReveal(TB.Reveal, TB.NpcId, Ctx)) { continue; }
                        if (TA.Stance == ETestimonyStance::Omits || TB.Stance == ETestimonyStance::Omits) { continue; }

                        bool bConflict = false;
                        std::string Reason;
                        if (TA.Stance == ETestimonyStance::Claims && TB.Stance == ETestimonyStance::Claims
                                && TA.ClaimText != TB.ClaimText)
                        {
                                bConflict = true;
                                Reason = "two different claims on one fact";
                        }
                        else if ((TA.Stance == ETestimonyStance::Affirms && TB.Stance != ETestimonyStance::Affirms)
                                || (TB.Stance == ETestimonyStance::Affirms && TA.Stance != ETestimonyStance::Affirms))
                        {
                                bConflict = true;
                        }
                        if (bConflict)
                        {
                                FactConflict C;
                                C.FactId = FactId;
                                C.NpcA = TA.NpcId;
                                C.NpcB = TB.NpcId;
                                // a deliberate lie explains itself; an honest disagreement
                                // stays flagged for the player to resolve
                                if (TA.bDeliberate) { C.Reason = TA.NpcId + ": " + TA.LieReason; }
                                else if (TB.bDeliberate) { C.Reason = TB.NpcId + ": " + TB.LieReason; }
                                else { C.Reason = "accounts disagree - neither declared a lie"; }
                                Out.push_back(C);
                        }
                }
        }
        return Out;
}

// ------------------------------------------------------------ transitions

void CaseFactSystem::ApplyLearned(const std::string& FactId, const std::string& Via, const std::string& FromNpc,
        int Day, int Hour, std::map<std::string, int>& OutFlagsToSet, std::string& OutError)
{
        OutError.clear();
        const CaseFactDef* Fact = FindFact(FactId);
        if (!Fact) { OutError = "unknown fact " + FactId; return; }
        if (Learned.count(FactId)) { return; }   // first learning wins; idempotent
        LearnedFact L;
        L.FactId = FactId;
        L.Day = Day;
        L.Hour = Hour;
        L.Via = Via;
        L.FromNpc = FromNpc;
        Learned[FactId] = L;
        OutFlagsToSet = Fact->OnLearnedFlags;
}

bool CaseFactSystem::NotifyTestimonyHeard(const std::string& FactId, const std::string& NpcId, int Day, int Hour,
        std::map<std::string, int>& OutFlagsToSet, std::string& OutError)
{
        OutFlagsToSet.clear();
        const TestimonyDef* T = FindTestimony(FactId, NpcId);
        if (!T) { OutError = "no testimony of " + FactId + " by " + NpcId; return false; }
        const std::string Key = FactId + "|" + NpcId;
        if (!HeardKey.count(Key))
        {
                HeardKey.insert(Key);
                HeardTestimony H;
                H.FactId = FactId;
                H.NpcId = NpcId;
                H.Day = Day;
                H.Hour = Hour;
                HeardLog.push_back(H);
        }
        if (!T->bGrantsFact)
        {
                // an honest-but-wrong account (or a silence) is heard but does not
                // teach the fact - the underlying truth stays consistent
                return true;
        }
        ApplyLearned(FactId, "testimony", NpcId, Day, Hour, OutFlagsToSet, OutError);
        return OutError.empty();
}

bool CaseFactSystem::NotifyFactLearned(const std::string& FactId, const std::string& Via, const std::string& FromNpc,
        int Day, int Hour, std::map<std::string, int>& OutFlagsToSet, std::string& OutError)
{
        OutFlagsToSet.clear();
        if (Via.empty()) { OutError = "fact learning requires a via source"; return false; }
        ApplyLearned(FactId, Via, FromNpc, Day, Hour, OutFlagsToSet, OutError);
        return OutError.empty();
}

// ------------------------------------------------------------ state queries

bool CaseFactSystem::IsLearned(const std::string& FactId) const
{
        return Learned.count(FactId) != 0;
}

const LearnedFact* CaseFactSystem::LearnRecord(const std::string& FactId) const
{
        auto It = Learned.find(FactId);
        return It == Learned.end() ? nullptr : &It->second;
}

bool CaseFactSystem::TestimonyHeard(const std::string& FactId, const std::string& NpcId) const
{
        return HeardKey.count(FactId + "|" + NpcId) != 0;
}

std::vector<std::string> CaseFactSystem::LearnedFactIds() const
{
        std::vector<std::string> Out;
        for (const auto& KV : Learned) { Out.push_back(KV.first); }
        return Out;
}

// ------------------------------------------------------------ save / load

JsonValue CaseFactSystem::SerializeState() const
{
        JsonValue Root = JsonValue::MakeObject();

        JsonValue LearnedArr = JsonValue::MakeArray();
        for (const auto& KV : Learned)
        {
                const LearnedFact& L = KV.second;
                JsonValue J = JsonValue::MakeObject();
                J.Set("fact", JsonValue(L.FactId));
                J.Set("day", JsonValue(L.Day));
                J.Set("hour", JsonValue(L.Hour));
                J.Set("via", JsonValue(L.Via));
                J.Set("from_npc", JsonValue(L.FromNpc));
                LearnedArr.Append(std::move(J));
        }
        Root.Set("learned", std::move(LearnedArr));

        JsonValue HeardArr = JsonValue::MakeArray();
        for (const HeardTestimony& H : HeardLog)
        {
                JsonValue J = JsonValue::MakeObject();
                J.Set("fact", JsonValue(H.FactId));
                J.Set("npc", JsonValue(H.NpcId));
                J.Set("day", JsonValue(H.Day));
                J.Set("hour", JsonValue(H.Hour));
                HeardArr.Append(std::move(J));
        }
        Root.Set("heard", std::move(HeardArr));

        return Root;
}

bool CaseFactSystem::DeserializeState(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "case state not an object"; return false; }
        Learned.clear();
        HeardLog.clear();
        HeardKey.clear();

        if (const JsonValue* L = Root.Find("learned"))
        {
                if (!L->IsArray()) { OutError = "case learned not an array"; return false; }
                for (size_t I = 0; I < L->Size(); ++I)
                {
                        const JsonValue* E = L->At(I);
                        if (!E || !E->IsObject()) { OutError = "case learned entry not an object"; return false; }
                        LearnedFact Rec;
                        Rec.FactId = E->GetString("fact", "");
                        if (Rec.FactId.empty()) { OutError = "case learned entry missing fact"; return false; }
                        if (!FindFact(Rec.FactId)) { OutError = "case learned references unknown fact " + Rec.FactId; return false; }
                        Rec.Day = E->GetInt("day", 1);
                        Rec.Hour = E->GetInt("hour", 8);
                        if (Rec.Day < 1 || Rec.Day > 9) { OutError = "case learned day out of range on " + Rec.FactId; return false; }
                        if (Rec.Hour < 0 || Rec.Hour > 24) { OutError = "case learned hour out of range on " + Rec.FactId; return false; }
                        Rec.Via = E->GetString("via", "");
                        if (Rec.Via.empty()) { OutError = "case learned missing via on " + Rec.FactId; return false; }
                        Rec.FromNpc = E->GetString("from_npc", "");
                        if (Learned.count(Rec.FactId)) { OutError = "case learned duplicate fact " + Rec.FactId; return false; }
                        Learned[Rec.FactId] = Rec;
                }
        }

        if (const JsonValue* H = Root.Find("heard"))
        {
                if (!H->IsArray()) { OutError = "case heard not an array"; return false; }
                for (size_t I = 0; I < H->Size(); ++I)
                {
                        const JsonValue* E = H->At(I);
                        if (!E || !E->IsObject()) { OutError = "case heard entry not an object"; return false; }
                        HeardTestimony Rec;
                        Rec.FactId = E->GetString("fact", "");
                        Rec.NpcId = E->GetString("npc", "");
                        if (Rec.FactId.empty() || Rec.NpcId.empty()) { OutError = "case heard entry missing fact/npc"; return false; }
                        if (!FindTestimony(Rec.FactId, Rec.NpcId)) { OutError = "case heard references unknown testimony " + Rec.FactId + "|" + Rec.NpcId; return false; }
                        Rec.Day = E->GetInt("day", 1);
                        Rec.Hour = E->GetInt("hour", 8);
                        if (Rec.Day < 1 || Rec.Day > 9) { OutError = "case heard day out of range"; return false; }
                        if (Rec.Hour < 0 || Rec.Hour > 24) { OutError = "case heard hour out of range"; return false; }
                        const std::string Key = Rec.FactId + "|" + Rec.NpcId;
                        if (HeardKey.count(Key)) { OutError = "case heard duplicate " + Key; return false; }
                        HeardKey.insert(Key);
                        HeardLog.push_back(Rec);
                }
        }
        return true;
}

} // namespace tls
