// THE LAST SIN: The Sin-Eater - M3.7
// TLSDeduction.cpp

#include "TLSDeduction.h"
#include "TLSCaseFacts.h"

namespace tls
{

const char* ToString(EAccusationTier T)
{
        switch (T)
        {
                case EAccusationTier::Baseless: return "baseless";
                case EAccusationTier::Partial:  return "partial";
                case EAccusationTier::Grounded: return "grounded";
        }
        return "baseless";
}

bool ParseAccusationTier(const std::string& S, EAccusationTier& Out)
{
        if (S == "baseless") { Out = EAccusationTier::Baseless; return true; }
        if (S == "partial")  { Out = EAccusationTier::Partial;  return true; }
        if (S == "grounded") { Out = EAccusationTier::Grounded; return true; }
        return false;
}

const char* ToString(EHypothesisVerdict V)
{
        switch (V)
        {
                case EHypothesisVerdict::Unsupported: return "unsupported";
                case EHypothesisVerdict::Partial:     return "partial";
                case EHypothesisVerdict::Supported:   return "supported";
                case EHypothesisVerdict::Refuted:     return "refuted";
        }
        return "unsupported";
}

// ------------------------------------------------------------ load

bool DeductionSystem::Load(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "deduction root must be an object"; return false; }

        const JsonValue* Hyps = Root.Find("hypotheses");
        if (!Hyps || !Hyps->IsArray()) { OutError = "missing 'hypotheses' array"; return false; }
        for (size_t I = 0; I < Hyps->Size(); ++I)
        {
                const JsonValue* H = Hyps->At(I);
                if (!H || !H->IsObject()) { OutError = "hypothesis entry not an object"; return false; }
                HypothesisDef Def;
                Def.Id = H->GetString("id", "");
                if (Def.Id.empty()) { OutError = "hypothesis missing id"; return false; }
                if (HypDefs.count(Def.Id)) { OutError = "duplicate hypothesis id " + Def.Id; return false; }
                Def.Title = H->GetString("title", "");
                Def.SuspectLabel = H->GetString("suspect_label", "");
                Def.SuspectNpc = H->GetString("suspect_npc", "");
                Def.MethodSummary = H->GetString("method", "");
                Def.MotiveSummary = H->GetString("motive", "");
                Def.RequiresInsights = H->GetStringList("requires_insights");
                Def.RequiresEvidence = H->GetStringList("requires_evidence");
                Def.RequiresFacts = H->GetStringList("requires_facts");
                Def.CanonRef = H->GetString("canon_ref", "");
                if (Def.Title.empty()) { OutError = "hypothesis " + Def.Id + " missing title"; return false; }
                if (Def.CanonRef.empty()) { OutError = "hypothesis " + Def.Id + " missing canon_ref"; return false; }
                if (Def.RequiresInsights.empty() && Def.RequiresEvidence.empty() && Def.RequiresFacts.empty())
                {
                        OutError = "hypothesis " + Def.Id + " has no support requirements (it could never be argued)";
                        return false;
                }
                if (const JsonValue* R = H->Find("refuted_by"))
                {
                        if (!R->IsArray()) { OutError = "hypothesis " + Def.Id + " refuted_by not an array"; return false; }
                        for (size_t K = 0; K < R->Size(); ++K)
                        {
                                const JsonValue* E = R->At(K);
                                if (!E || !E->IsObject()) { OutError = "hypothesis " + Def.Id + " refuter not an object"; return false; }
                                HypothesisDef::Refuter Ref;
                                std::string KindStr = E->GetString("type", "");
                                if (KindStr == "flag") { Ref.KindV = HypothesisDef::Refuter::Kind::Flag; }
                                else if (KindStr == "fact") { Ref.KindV = HypothesisDef::Refuter::Kind::Fact; }
                                else if (KindStr == "contradiction") { Ref.KindV = HypothesisDef::Refuter::Kind::Contradiction; }
                                else if (KindStr == "player_rumor") { Ref.KindV = HypothesisDef::Refuter::Kind::PlayerRumor; }
                                else { OutError = "hypothesis " + Def.Id + " refuter bad type '" + KindStr + "'"; return false; }
                                Ref.Target = E->GetString("target", "");
                                if (Ref.Target.empty()) { OutError = "hypothesis " + Def.Id + " refuter missing target"; return false; }
                                Ref.Reason = E->GetString("reason", "");
                                if (Ref.Reason.empty()) { OutError = "hypothesis " + Def.Id + " refuter " + Ref.Target + " missing reason"; return false; }
                                Def.RefutedBy.push_back(Ref);
                        }
                }
                HypDefs[Def.Id] = Def;
        }

        const JsonValue* Accs = Root.Find("accusations");
        if (!Accs || !Accs->IsArray()) { OutError = "missing 'accusations' array"; return false; }
        for (size_t I = 0; I < Accs->Size(); ++I)
        {
                const JsonValue* A = Accs->At(I);
                if (!A || !A->IsObject()) { OutError = "accusation entry not an object"; return false; }
                AccusationDef Def;
                Def.Id = A->GetString("id", "");
                if (Def.Id.empty()) { OutError = "accusation missing id"; return false; }
                if (AccDefs.count(Def.Id)) { OutError = "duplicate accusation id " + Def.Id; return false; }
                Def.TargetLabel = A->GetString("target_label", "");
                Def.TargetNpc = A->GetString("target_npc", "");
                Def.Topic = A->GetString("topic", "");
                Def.bAlwaysBaseless = A->GetBool("baseless", false);
                Def.GroundingInsight = A->GetString("grounding_insight", "");
                Def.GroundingEvidence = A->GetStringList("grounding_evidence");
                Def.GroundingFact = A->GetString("grounding_fact", "");
                Def.MinReliability = A->GetNumber("min_reliability", 0.0);
                Def.bRepeatable = A->GetBool("repeatable", false);
                std::string MaxStr = A->GetString("max_tier", "grounded");
                if (!ParseAccusationTier(MaxStr, Def.MaxTier) || Def.MaxTier == EAccusationTier::Baseless)
                {
                        OutError = "accusation " + Def.Id + " bad max_tier '" + MaxStr + "'";
                        return false;
                }
                Def.CanonRef = A->GetString("canon_ref", "");
                if (Def.TargetLabel.empty() || Def.Topic.empty()) { OutError = "accusation " + Def.Id + " missing target_label/topic"; return false; }
                if (Def.CanonRef.empty()) { OutError = "accusation " + Def.Id + " missing canon_ref"; return false; }
                if (Def.bAlwaysBaseless)
                {
                        if (!Def.GroundingInsight.empty() || !Def.GroundingEvidence.empty() || !Def.GroundingFact.empty())
                        {
                                OutError = "accusation " + Def.Id + " declares baseless but carries grounding fields";
                                return false;
                        }
                }
                else if (Def.GroundingInsight.empty() && Def.GroundingEvidence.empty() && Def.GroundingFact.empty())
                {
                        OutError = "accusation " + Def.Id + " has no grounding fields (declare \"baseless\": true, or give a bundle)";
                        return false;
                }

                auto LoadConsequences = [](const JsonValue* Node, AccusationConsequences& Out, std::string& Err, const std::string& AccId, const char* Which) -> bool
                {
                        if (!Node) { return true; }   // empty consequences allowed (a tier may cost nothing but silence)
                        if (!Node->IsObject()) { Err = std::string("accusation ") + AccId + " " + Which + " not an object"; return false; }
                        Out.TrustDeltaTarget = Node->GetNumber("trust_delta_target", 0.0);
                        Out.TensionDelta = Node->GetNumber("tension_delta", 0.0);
                        Out.ReputationDelta = Node->GetNumber("reputation_delta", 0.0);
                        Out.JournalNote = Node->GetString("journal_note", "");
                        if (const JsonValue* F = Node->Find("set_flags"))
                        {
                                if (!F->IsObject()) { Err = std::string("accusation ") + AccId + " " + Which + " set_flags not an object"; return false; }
                                for (const auto& KV : F->AsObject())
                                {
                                        if (!KV.second.IsNumber()) { Err = std::string("accusation ") + AccId + " " + Which + " flag value not a number"; return false; }
                                        Out.SetFlags[KV.first] = KV.second.AsInt();
                                }
                        }
                        return true;
                };
                if (!LoadConsequences(A->Find("on_grounded"), Def.OnGrounded, OutError, Def.Id, "on_grounded")) { return false; }
                if (!LoadConsequences(A->Find("on_partial"), Def.OnPartial, OutError, Def.Id, "on_partial")) { return false; }
                if (!LoadConsequences(A->Find("on_baseless"), Def.OnBaseless, OutError, Def.Id, "on_baseless")) { return false; }
                AccDefs[Def.Id] = Def;
        }
        return true;
}

// ------------------------------------------------------------ queries

const HypothesisDef* DeductionSystem::FindHypothesis(const std::string& Id) const
{
        auto It = HypDefs.find(Id);
        return It == HypDefs.end() ? nullptr : &It->second;
}

const AccusationDef* DeductionSystem::FindAccusation(const std::string& Id) const
{
        auto It = AccDefs.find(Id);
        return It == AccDefs.end() ? nullptr : &It->second;
}

// ------------------------------------------------------------ hypotheses

bool DeductionSystem::FormHypothesis(const std::string& HypId, int Day, std::string& OutError)
{
        const HypothesisDef* Def = FindHypothesis(HypId);
        if (!Def) { OutError = "unknown hypothesis " + HypId; return false; }
        if (FormedMap.count(HypId)) { OutError = "hypothesis already formed: " + HypId; return false; }
        FormedHypothesis F;
        F.HypId = HypId;
        F.DayFormed = Day;
        F.LastEvalDay = Day;
        F.Verdict = EHypothesisVerdict::Unsupported;
        FormedMap[HypId] = F;
        return true;
}

bool DeductionSystem::IsFormed(const std::string& HypId) const
{
        return FormedMap.count(HypId) != 0;
}

const FormedHypothesis* DeductionSystem::Formed(const std::string& HypId) const
{
        auto It = FormedMap.find(HypId);
        return It == FormedMap.end() ? nullptr : &It->second;
}

std::vector<FormedHypothesis> DeductionSystem::FormedList() const
{
        std::vector<FormedHypothesis> Out;
        for (const auto& KV : FormedMap) { Out.push_back(KV.second); }
        return Out;
}

EHypothesisVerdict DeductionSystem::Evaluate(const HypothesisDef& Hyp, const IGameContext& Ctx,
        const CaseFactSystem& Facts, std::string& OutRefuteReason) const
{
        OutRefuteReason.clear();
        for (const HypothesisDef::Refuter& R : Hyp.RefutedBy)
        {
                bool bFired = false;
                switch (R.KindV)
                {
                        case HypothesisDef::Refuter::Kind::Flag:
                                bFired = Ctx.GetFlag(R.Target) != 0;
                                break;
                        case HypothesisDef::Refuter::Kind::Fact:
                                bFired = Facts.IsLearned(R.Target);
                                break;
                        case HypothesisDef::Refuter::Kind::Contradiction:
                                bFired = Ctx.ContradictionRuleDrawn(R.Target);
                                break;
                        case HypothesisDef::Refuter::Kind::PlayerRumor:
                                bFired = Ctx.PlayerHeardRumor(R.Target);
                                break;
                }
                if (bFired) { OutRefuteReason = R.Reason; return EHypothesisVerdict::Refuted; }
        }

        size_t Have = 0, Need = 0;
        for (const std::string& In : Hyp.RequiresInsights) { ++Need; if (Ctx.InsightKnown(In)) { ++Have; } }
        for (const std::string& Ev : Hyp.RequiresEvidence) { ++Need; if (Ctx.EvidenceCollected(Ev)) { ++Have; } }
        for (const std::string& Fa : Hyp.RequiresFacts) { ++Need; if (Facts.IsLearned(Fa)) { ++Have; } }

        if (Have == Need) { return EHypothesisVerdict::Supported; }
        if (Have > 0) { return EHypothesisVerdict::Partial; }
        return EHypothesisVerdict::Unsupported;
}

void DeductionSystem::RecheckAll(const IGameContext& Ctx, const CaseFactSystem& Facts, int Day)
{
        for (auto& KV : FormedMap)
        {
                FormedHypothesis& F = KV.second;
                std::string Reason;
                F.Verdict = Evaluate(*FindHypothesis(F.HypId), Ctx, Facts, Reason);
                // a collapse is permanent for this session - a refuted hypothesis
                // does not resurrect when a later edit changes unrelated state
                if (F.Verdict == EHypothesisVerdict::Refuted)
                {
                        F.RefuteReason = Reason;
                }
                else if (!F.RefuteReason.empty())
                {
                        F.Verdict = EHypothesisVerdict::Refuted;
                }
                F.LastEvalDay = Day;
        }
}

std::vector<OpenQuestion> DeductionSystem::OpenQuestions(const IGameContext& Ctx, const CaseFactSystem& Facts) const
{
        std::vector<OpenQuestion> Out;
        for (const auto& KV : FormedMap)
        {
                const FormedHypothesis& F = KV.second;
                if (F.Verdict == EHypothesisVerdict::Refuted || F.Verdict == EHypothesisVerdict::Supported) { continue; }
                const HypothesisDef* Def = FindHypothesis(F.HypId);
                if (!Def) { continue; }
                for (const std::string& In : Def->RequiresInsights)
                {
                        if (!Ctx.InsightKnown(In))
                        {
                                OpenQuestion Q; Q.HypId = F.HypId; Q.Kind = "insight"; Q.TargetId = In;
                                Q.Question = "Which connection would prove: " + Def->Title + "?";
                                Out.push_back(Q);
                        }
                }
                for (const std::string& Ev : Def->RequiresEvidence)
                {
                        if (!Ctx.EvidenceCollected(Ev))
                        {
                                OpenQuestion Q; Q.HypId = F.HypId; Q.Kind = "evidence"; Q.TargetId = Ev;
                                Q.Question = "What physical record would test: " + Def->Title + "?";
                                Out.push_back(Q);
                        }
                }
                for (const std::string& Fa : Def->RequiresFacts)
                {
                        if (!Facts.IsLearned(Fa))
                        {
                                OpenQuestion Q; Q.HypId = F.HypId; Q.Kind = "fact"; Q.TargetId = Fa;
                                Q.Question = "What does the village know that bears on: " + Def->Title + "?";
                                Out.push_back(Q);
                        }
                }
        }
        return Out;
}

// ------------------------------------------------------------ accusations

EAccusationTier DeductionSystem::EvaluateTier(const AccusationDef& Def, const IGameContext& Ctx,
        const CaseFactSystem& Facts) const
{
        if (Def.bAlwaysBaseless)
        {
                return EAccusationTier::Baseless;
        }

        const bool bInsight = Def.GroundingInsight.empty() || Ctx.InsightKnown(Def.GroundingInsight);
        const bool bHasInsightField = !Def.GroundingInsight.empty();
        size_t EvHave = 0;
        double RelSum = 0.0;
        for (const std::string& Ev : Def.GroundingEvidence)
        {
                double Rel = 0.0;
                if (Ctx.EvidenceCollected(Ev) && Ctx.EvidenceReliability(Ev, Rel)) { ++EvHave; RelSum += Rel; }
        }
        const bool bBundle = EvHave == Def.GroundingEvidence.size();
        const bool bHasBundleField = !Def.GroundingEvidence.empty();
        const bool bReliability = !bHasBundleField
                || (EvHave == Def.GroundingEvidence.size()
                        && (RelSum / static_cast<double>(Def.GroundingEvidence.size())) >= Def.MinReliability);
        const bool bFact = Def.GroundingFact.empty() || Facts.IsLearned(Def.GroundingFact);
        const bool bHasFactField = !Def.GroundingFact.empty();

        const bool bAll = bInsight && bBundle && bReliability && bFact;
        const bool bAny = (bHasInsightField && bInsight) || (bHasBundleField && bBundle && bReliability) || (bHasFactField && bFact);

        EAccusationTier Tier = EAccusationTier::Baseless;
        if (bAll)
        {
                Tier = EAccusationTier::Grounded;
        }
        else if (bAny)
        {
                Tier = EAccusationTier::Partial;
        }
        if (Tier > Def.MaxTier) { Tier = Def.MaxTier; }
        return Tier;
}

EAccusationTier DeductionSystem::PreviewTier(const std::string& AccId, const IGameContext& Ctx,
        const CaseFactSystem& Facts) const
{
        // The accusation UI's honest strength readout: the exact tier the
        // accusation WOULD land at, computed from live state - without
        // recording anything and without any consequence. Unknown ids fall
        // back to Baseless; the UI refuses those before display.
        const AccusationDef* Def = FindAccusation(AccId);
        if (!Def) { return EAccusationTier::Baseless; }
        return EvaluateTier(*Def, Ctx, Facts);
}

bool DeductionSystem::MakeAccusation(const std::string& AccId, const IGameContext& Ctx, const CaseFactSystem& Facts,
        int Day, int Hour, EAccusationTier& OutTier, std::string& OutError)
{
        const AccusationDef* Def = FindAccusation(AccId);
        if (!Def) { OutError = "unknown accusation " + AccId; return false; }
        if (!Def->bRepeatable && AccUsed.count(AccId))
        {
                OutError = "the words are already out: " + AccId;
                return false;
        }

        OutTier = EvaluateTier(*Def, Ctx, Facts);

        AccusationRecord Rec;
        Rec.AccId = AccId;
        Rec.Tier = OutTier;
        Rec.Day = Day;
        Rec.Hour = Hour;
        AccLog.push_back(Rec);
        AccUsed.insert(AccId);
        return true;
}

bool DeductionSystem::AccusedBefore(const std::string& AccId) const
{
        return AccUsed.count(AccId) != 0;
}

// ------------------------------------------------------------ save / load

JsonValue DeductionSystem::SerializeState() const
{
        JsonValue Root = JsonValue::MakeObject();

        JsonValue FormedArr = JsonValue::MakeArray();
        for (const auto& KV : FormedMap)
        {
                const FormedHypothesis& F = KV.second;
                JsonValue J = JsonValue::MakeObject();
                J.Set("hyp", JsonValue(F.HypId));
                J.Set("day_formed", JsonValue(F.DayFormed));
                J.Set("last_eval_day", JsonValue(F.LastEvalDay));
                J.Set("verdict", JsonValue(std::string(ToString(F.Verdict))));
                J.Set("refute_reason", JsonValue(F.RefuteReason));
                FormedArr.Append(std::move(J));
        }
        Root.Set("formed", std::move(FormedArr));

        JsonValue AccArr = JsonValue::MakeArray();
        for (const AccusationRecord& R : AccLog)
        {
                JsonValue J = JsonValue::MakeObject();
                J.Set("acc", JsonValue(R.AccId));
                J.Set("tier", JsonValue(std::string(ToString(R.Tier))));
                J.Set("day", JsonValue(R.Day));
                J.Set("hour", JsonValue(R.Hour));
                AccArr.Append(std::move(J));
        }
        Root.Set("accusations", std::move(AccArr));

        return Root;
}

bool DeductionSystem::DeserializeState(const JsonValue& Root, std::string& OutError)
{
        if (!Root.IsObject()) { OutError = "deduction state not an object"; return false; }
        FormedMap.clear();
        AccLog.clear();
        AccUsed.clear();

        if (const JsonValue* F = Root.Find("formed"))
        {
                if (!F->IsArray()) { OutError = "deduction formed not an array"; return false; }
                for (size_t I = 0; I < F->Size(); ++I)
                {
                        const JsonValue* E = F->At(I);
                        if (!E || !E->IsObject()) { OutError = "deduction formed entry not an object"; return false; }
                        FormedHypothesis Rec;
                        Rec.HypId = E->GetString("hyp", "");
                        if (Rec.HypId.empty()) { OutError = "deduction formed entry missing hyp"; return false; }
                        if (!FindHypothesis(Rec.HypId)) { OutError = "deduction formed references unknown hypothesis " + Rec.HypId; return false; }
                        Rec.DayFormed = E->GetInt("day_formed", 1);
                        Rec.LastEvalDay = E->GetInt("last_eval_day", 1);
                        if (Rec.DayFormed < 1 || Rec.DayFormed > 9 || Rec.LastEvalDay < 1 || Rec.LastEvalDay > 9)
                        {
                                OutError = "deduction formed day out of range on " + Rec.HypId;
                                return false;
                        }
                        std::string VerdictStr = E->GetString("verdict", "unsupported");
                        if (VerdictStr == "unsupported") { Rec.Verdict = EHypothesisVerdict::Unsupported; }
                        else if (VerdictStr == "partial") { Rec.Verdict = EHypothesisVerdict::Partial; }
                        else if (VerdictStr == "supported") { Rec.Verdict = EHypothesisVerdict::Supported; }
                        else if (VerdictStr == "refuted") { Rec.Verdict = EHypothesisVerdict::Refuted; }
                        else { OutError = "deduction formed bad verdict '" + VerdictStr + "' on " + Rec.HypId; return false; }
                        Rec.RefuteReason = E->GetString("refute_reason", "");
                        if (Rec.Verdict == EHypothesisVerdict::Refuted && Rec.RefuteReason.empty())
                        {
                                OutError = "deduction formed refuted without reason on " + Rec.HypId;
                                return false;
                        }
                        if (FormedMap.count(Rec.HypId)) { OutError = "deduction formed duplicate hypothesis " + Rec.HypId; return false; }
                        FormedMap[Rec.HypId] = Rec;
                }
        }

        if (const JsonValue* A = Root.Find("accusations"))
        {
                if (!A->IsArray()) { OutError = "deduction accusations not an array"; return false; }
                for (size_t I = 0; I < A->Size(); ++I)
                {
                        const JsonValue* E = A->At(I);
                        if (!E || !E->IsObject()) { OutError = "deduction accusation entry not an object"; return false; }
                        AccusationRecord Rec;
                        Rec.AccId = E->GetString("acc", "");
                        if (Rec.AccId.empty()) { OutError = "deduction accusation entry missing acc"; return false; }
                        if (!FindAccusation(Rec.AccId)) { OutError = "deduction accusation references unknown accusation " + Rec.AccId; return false; }
                        std::string TierStr = E->GetString("tier", "baseless");
                        if (!ParseAccusationTier(TierStr, Rec.Tier)) { OutError = "deduction accusation bad tier on " + Rec.AccId; return false; }
                        Rec.Day = E->GetInt("day", 1);
                        Rec.Hour = E->GetInt("hour", 8);
                        if (Rec.Day < 1 || Rec.Day > 9 || Rec.Hour < 0 || Rec.Hour > 24)
                        {
                                OutError = "deduction accusation day/hour out of range on " + Rec.AccId;
                                return false;
                        }
                        AccLog.push_back(Rec);
                        AccUsed.insert(Rec.AccId);
                }
        }
        return true;
}

} // namespace tls
