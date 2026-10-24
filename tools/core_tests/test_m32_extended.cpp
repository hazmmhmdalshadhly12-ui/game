// THE LAST SIN: The Sin-Eater - M3.2
// test_m32_extended: the second investigation milestone. Extends the M3.1
// loop harness (never forks it) with the parts of the game the first loop
// did not touch, using ONLY existing systems and the story data already in
// the repo (no invented events, no simplified copies):
//
//   - the unvisited interrogations: Rev. Crane's full tree (incl. the day-2
//     gated tower-night topic and the dish DENIAL reaction), Mair Wen Ari
//     (the only negative-tone choices in the slice), Coles' hunger babble
//     and register acceptance, Ifor's day-1-only Trefan topic, Gwendolyn's
//     trust-gated guinea topic from BOTH sides (closed below 20, open above)
//   - the board paths M3.1 never drew: INS-REFUSAL via ledger+witness,
//     INS-SINLIST via rite-paper+guinea, INS-PATTERN via fraud+body, the
//     two SUPPORTING rules (no insight) and the two CONTRADICTION rules
//     still untested (hunger+footprints, sermon+weights), plus the
//     duplicate-path draw (second route to a known insight)
//   - the any_of alibi closed through the WITNESS branch (a villager
//     carries the moor-road account) while the player never hears it
//   - rumor conflict detection (same topic, opposite valence) in-loop
//   - multi-day decay/forget watch: the leaked word dies, the direct
//     witness's confidence follows the exact per-rumor decay curve
//   - order independence: the same day-1 interaction set in two orders
//     lands on the same canonical state (no contradictory states)
//   - save/restore expansion: multi-cycle byte stability, ghost-id and
//     bad-status refusals (now atomic refusals at the engine level),
//     empty-vs-absent section equivalence, missing required sections,
//     load-during-dialogue, and the sim-RNG seam
//   - a failed urgent quest cannot be resurrected by later knowledge

#include "tls_test_framework.h"
#include "test_fixtures.h"

#include "TLSGameState.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

using namespace tls;

namespace tls_test_m32
{

namespace
{

// Picks the first available choice whose id matches (finds it among the
// CONDITION-FILTERED list - exactly like the UI does).
bool PickChoice(Game& G, const std::string& ChoiceId, std::string& Err)
{
        std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
        for (size_t I = 0; I < Avail.size(); ++I)
        {
                if (Avail[I]->Id == ChoiceId)
                {
                        std::string Entered;
                        return G.PickDialogueChoice(I, Entered, Err);
                }
        }
        Err = "choice not available (conditions unmet or wrong node): " + ChoiceId;
        return false;
}

bool ChoiceAvailable(Game& G, const std::string& ChoiceId)
{
        std::vector<const DialogueChoice*> Avail = G.DialogueAvailableChoices();
        for (const DialogueChoice* C : Avail)
        {
                if (C && C->Id == ChoiceId) { return true; }
        }
        return false;
}

bool ObjectiveDone(Game& G, const std::string& ObjectiveId)
{
        for (const QuestSystem::QuestProgressLine& L : G.Quests().ProgressLines())
        {
                if (L.ObjectiveId == ObjectiveId) { return L.bObjectiveDone; }
        }
        return false;
}

std::string TrustText(double V)
{
        char Buf[32];
        std::snprintf(Buf, sizeof(Buf), "%.4f", V);
        return Buf;
}

// The canonical semantic state of a session: everything the design treats as
// truth, in a stable order. Deliberately EXCLUDES the journal (its entry
// order legitimately follows the player's choice order) - so two different
// interaction ORDERS over the same interaction SET compare equal here.
std::string CanonicalSignature(const Game& G)
{
        std::ostringstream Out;
        Out << "day=" << G.CurrentDay()
                << ";weather=" << static_cast<int>(G.GetWeather())
                << ";time=" << static_cast<int>(G.GetTimeOfDay())
                << ";tension=" << TrustText(G.GetTension())
                << ";rep=" << TrustText(G.Village().Reputation());

        Out << ";trust=";
        for (const auto& KV : G.Village().Npcs())
        {
                Out << KV.first << ":" << TrustText(G.GetTrust(KV.first)) << ",";
        }

        Out << ";flags=";
        for (const auto& KV : G.Flags())
        {
                Out << KV.first << "=" << KV.second << ",";
        }

        Out << ";areas=";
        {
                std::vector<std::string> A;
                for (const std::string& Area : { "AREA-CHURCHYARD", "AREA-BOUNDARY", "AREA-COTTAGE", "AREA-MILL", "AREA-SQUARE" })
                {
                        if (G.HasReachedArea(Area)) { A.push_back(Area); }
                }
                std::sort(A.begin(), A.end());
                for (const std::string& Area : A) { Out << Area << ","; }
        }

        Out << ";evidence=";
        for (const auto& KV : G.Evidence().Defs())
        {
                const EvidenceRuntime* R = G.Evidence().State(KV.first);
                Out << KV.first << ":";
                if (R)
                {
                        Out << (R->bObserved ? "O" : "-") << (R->bCollected ? "C" : "-")
                                << (R->bExamined ? "E" : "-") << (R->bRestored ? "R" : "-")
                                << "@d" << R->DayCollected << ";custody=" << R->ChainOfCustody.size();
                }
                else
                {
                        Out << "fresh";
                }
                Out << ",";
        }

        Out << ";insights=";
        for (const auto& KV : G.Evidence().Insights())
        {
                Out << KV.first << (G.InsightKnown(KV.first) ? ":known," : ":no,");
        }

        Out << ";links=";
        {
                std::vector<std::string> Rules;
                for (const DrawnLink& L : G.Evidence().Links()) { Rules.push_back(L.RuleId); }
                std::sort(Rules.begin(), Rules.end());
                for (const std::string& R : Rules) { Out << R << ","; }
        }

        Out << ";quests=";
        for (const char* QId : { "Q-M-C1", "Q-M-C2a", "Q-M-C3", "Q-S-C3-SHONI" })
        {
                Out << QId << "=" << static_cast<int>(G.Quests().Status(QId)) << ",";
        }

        Out << ";rumors=";
        for (const auto& KV : G.Rumors().Defs())
        {
                Out << KV.first << ":" << G.Rumors().KnowerCount(KV.first) << ",";
        }

        Out << ";player_rumors=";
        for (const std::string& R : G.Rumors().PlayerKnownRumors()) { Out << R << ","; }

        return Out.str();
}

// Value-replacement / section surgery on serialized payloads (same technique
// as the M2 corruption tests and the M3.1 atomic-refusal battery).
bool ReplaceSectionValue(const std::string& Payload, const char* Key, const char* NewValue, std::string& Out)
{
        Out = Payload;
        const size_t KeyPos = Out.find(std::string("\"") + Key + "\":");
        if (KeyPos == std::string::npos) { return false; }
        const size_t ValueStart = Out.find(':', KeyPos) + 1;
        const char First = Out[ValueStart];
        size_t ValueEnd = ValueStart;
        if (First == '"')
        {
                ValueEnd = Out.find('"', ValueStart + 1);
        }
        else if (First == '{' || First == '[')
        {
                const char Open = First;
                const char Close = (First == '{') ? '}' : ']';
                int Depth = 0;
                for (size_t S = ValueStart; S < Out.size(); ++S)
                {
                        if (Out[S] == Open) { ++Depth; }
                        else if (Out[S] == Close)
                        {
                                --Depth;
                                if (Depth == 0) { ValueEnd = S; break; }
                        }
                }
        }
        else
        {
                ValueEnd = Out.find(',', ValueStart) - 1;
        }
        if (ValueEnd == std::string::npos || ValueEnd < ValueStart) { return false; }
        Out.replace(ValueStart, ValueEnd - ValueStart + 1, NewValue);
        return true;
}

// Removes a whole top-level section (key + value) from a serialized payload.
bool RemoveSection(const std::string& Payload, const char* Key, std::string& Out)
{
        Out = Payload;
        const std::string Needle = std::string("\"") + Key + "\":";
        const size_t KeyPos = Out.find(Needle);
        if (KeyPos == std::string::npos) { return false; }
        const size_t ValueStart = Out.find(':', KeyPos) + 1;
        const char First = Out[ValueStart];
        const char Close = (First == '{') ? '}' : ((First == '[') ? ']' : '"');
        size_t ValueEnd = ValueStart;
        if (First == '{' || First == '[')
        {
                int Depth = 0;
                for (size_t S = ValueStart; S < Out.size(); ++S)
                {
                        if (Out[S] == First) { ++Depth; }
                        else if (Out[S] == Close)
                        {
                                --Depth;
                                if (Depth == 0) { ValueEnd = S; break; }
                        }
                }
        }
        else
        {
                ValueEnd = Out.find('"', ValueStart + 1);
        }
        if (ValueEnd == std::string::npos) { return false; }
        size_t End = ValueEnd + 1;
        if (End < Out.size() && Out[End] == ',') { ++End; }
        Out.erase(KeyPos, End - KeyPos);
        return true;
}

// Inserts a raw item right after the opening bracket of an array section.
bool InjectIntoArray(const std::string& Payload, const char* Key, const char* Item, std::string& Out)
{
        Out = Payload;
        const size_t KeyPos = Out.find(std::string("\"") + Key + "\":[");
        if (KeyPos == std::string::npos) { return false; }
        const size_t InsertAt = KeyPos + std::strlen(Key) + 4;
        Out.insert(InsertAt, Item);
        return true;
}

// Inserts a raw item right before the closing bracket of an array section
// (array order matters on resave - the serializer re-sorts sets).
bool AppendIntoArray(const std::string& Payload, const char* Key, const char* Item, std::string& Out)
{
        Out = Payload;
        const size_t KeyPos = Out.find(std::string("\"") + Key + "\":[");
        if (KeyPos == std::string::npos) { return false; }
        const size_t ArrayStart = KeyPos + std::strlen(Key) + 4;
        const size_t ArrayEnd = Out.find(']', ArrayStart);
        if (ArrayEnd == std::string::npos) { return false; }
        Out.insert(ArrayEnd, Item);
        return true;
}

} // anonymous namespace

// ------------------------------------------------------- the extended loop

void RunExtendedLoop(Game& G)
{
        std::string Err, Note, Reveal, Msg, SleepReason;
        std::vector<std::string> NI;

        // ------------------------------------------------ day 1 (C1)
        TLS_SECTION("M3.2 loop - day 1: the full round of interrogations");

        G.NewGame();
        TLS_CHECK(G.CurrentDay() == 1);
        TLS_CHECK(G.GetWeather() == EWeather::OvercastFog);
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Active);
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::NotStarted);

        // the churchyard first: the register is observed AND taken (Coles will
        // only accept it later - has_evidence gates the register choice)
        G.NotifyReachArea("AREA-CHURCHYARD");
        G.NotifyObserveEvidence("EVD-GRAVE", &Note);
        TLS_CHECK_MSG(Note.find("decline of years") != std::string::npos, "grave register line");
        G.NotifyCollectEvidence("EVD-GRAVE", "the parish register, borrowed without asking");
        TLS_CHECK(G.EvidenceCollected("EVD-GRAVE"));

        // Ifor's day-1 topic: the Trefan moor-road (day_max 1 - gone tomorrow)
        TLS_CHECK(G.BeginDialogue("DLG-IFOR-C2", Err));
        TLS_CHECK_MSG(ChoiceAvailable(G, "I1"), "Ifor's Trefan topic is a day-1 topic");
        TLS_CHECK(PickChoice(G, "I1", Err));
        TLS_CHECK(G.GetFlag("TOP_TREFAN") == 1);
        TLS_CHECK(!G.DialogueRunning());

        // the trust gate, closed side: one polite exchange with Gwendolyn does
        // NOT unlock her guinea-paper topic (trust_min 20)
        TLS_CHECK(G.BeginDialogue("DLG-GWENDOLYN-C1", Err));
        TLS_CHECK(PickChoice(G, "G01", Err));                       // gentle +2 (+tone) - below the gate
        TLS_CHECK_MSG(!ChoiceAvailable(G, "H2"),
                "the guinea topic stays shut while Gwendolyn's trust is below 20");
        TLS_CHECK(PickChoice(G, "H6", Err));
        TLS_CHECK(!G.DialogueRunning());

        // Coles: the hunger babble is a ROOT choice (grants the folklore claim
        // the board will later REFUTE); the sign conversation is another visit
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        TLS_CHECK(PickChoice(G, "B3", Err));
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-HUNGER"));
        TLS_CHECK(PickChoice(G, "BH4", Err));
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        TLS_CHECK(PickChoice(G, "B2", Err));
        TLS_CHECK(PickChoice(G, "BH4", Err));

        // Mair: the pressing question costs exactly 4.0 trust (pressing tone
        // -5 + delta -3, halved by her 0.5 relationship bias), then the kind
        // one gives 1.0 back
        TLS_CHECK(G.BeginDialogue("DLG-MAIR-C1", Err));
        TLS_CHECK(G.GetFlag("MET_MAIR") == 1);
        {
                const double Before = G.GetTrust("CHR-06");
                TLS_CHECK(PickChoice(G, "M3", Err));
                TLS_CHECK_MSG(G.GetTrust("CHR-06") == Before - 4.0,
                        "Mair's pressing tone applies the documented delta math");
        }
        TLS_CHECK(G.BeginDialogue("DLG-MAIR-C1", Err));
        TLS_CHECK(PickChoice(G, "M1", Err));
        TLS_CHECK(G.GetTrust("CHR-06") == -3.0);

        // Crane: the gentle path, the list topic from the hub
        TLS_CHECK(G.BeginDialogue("DLG-CRANE-C1", Err));
        TLS_CHECK(G.GetFlag("MET_CRANE") == 1);
        TLS_CHECK(PickChoice(G, "C02", Err));
        TLS_CHECK(PickChoice(G, "CH1", Err));
        TLS_CHECK(G.GetFlag("TOP_LIST") == 1);
        TLS_CHECK_MSG(!G.EvidenceCollected("EVD-CRANE-SERMON"),
                "the sermon comes with C01, not C02 - the loop keeps it uncollected for now");

        // the day-1 ground evidence
        G.NotifyReachArea("AREA-BOUNDARY");
        G.NotifyCollectEvidence("EVD-DISH", "taken from beside the boundary stone");
        G.NotifyReachArea("AREA-COTTAGE");
        G.NotifyCollectEvidence("EVD-LEDGER", "lifted from under the engraving table");
        G.NotifyCollectEvidence("EVD-RITE-PAPER", "taken from the shelf above the hearth");
        G.NotifyCollectEvidence("EVD-TORN-PAGE", "prised from beneath the floor stone");
        G.NotifyRestorePage("EVD-TORN-PAGE", &Reveal);
        TLS_CHECK_MSG(Reveal.find("The bread stayed on the stone") != std::string::npos, "restored page");

        // the Black Ram, again from the top: the dish opens the hub, and with
        // G04+H1 the trust crosses 20 - the gate OPENS (closed side checked above)
        TLS_CHECK(G.BeginDialogue("DLG-GWENDOLYN-C1", Err));
        TLS_CHECK(PickChoice(G, "G04", Err));                       // present the dish (accept)
        TLS_CHECK(PickChoice(G, "H1", Err));                        // the last tray
        TLS_CHECK(G.EvidenceCollected("EVD-GWEN-LASTNIGHT"));
        {
                const double Trust = G.GetTrust("CHR-03");
                TLS_CHECK_MSG(Trust >= 20.0, "G04+H1 carried Gwendolyn past the gate");
                TLS_CHECK_MSG(ChoiceAvailable(G, "H2"), "the guinea topic unlocks at trust >= 20");
        }
        TLS_CHECK(PickChoice(G, "H2", Err));
        TLS_CHECK(G.EvidenceCollected("EVD-GWEN-GUINEA"));
        TLS_CHECK(PickChoice(G, "H3", Err));                        // the Mair topic
        TLS_CHECK(PickChoice(G, "H4", Err));                        // the ledger topic (accept)
        TLS_CHECK(PickChoice(G, "H6", Err));

        // Coles' hub: the last-months topic (the rite testimony) and the
        // register acceptance - has_evidence EVD-GRAVE is now satisfied
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        TLS_CHECK(PickChoice(G, "B1", Err));
        TLS_CHECK(PickChoice(G, "BH1", Err));
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-RITE"));
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        TLS_CHECK(PickChoice(G, "B4", Err));                        // present the register (accept)
        TLS_CHECK(PickChoice(G, "BH4", Err));

        // the interrogation reaction: Crane DENIES the dish - the contradiction
        // lands in the dish's chain of custody
        {
                const EvidenceRuntime* R = G.Evidence().State("EVD-DISH");
                TLS_CHECK(R != nullptr);
                const size_t CustodyBefore = R ? R->ChainOfCustody.size() : 0;
                TLS_CHECK(G.BeginDialogue("DLG-CRANE-C1", Err));
                TLS_CHECK(PickChoice(G, "C03", Err));               // present the dish - DENIED
                TLS_CHECK(PickChoice(G, "CH4", Err));
                R = G.Evidence().State("EVD-DISH");
                TLS_CHECK(R != nullptr && R->ChainOfCustody.size() == CustodyBefore + 1);
                TLS_CHECK_MSG(R && R->ChainOfCustody.back().find("denied it") != std::string::npos,
                        "a denial is recorded in the custody chain");
        }

        // the father's table
        G.NotifyExamineEvidence("EVD-DISH", &Reveal);
        G.NotifyExamineEvidence("EVD-LEDGER", &Reveal);
        G.NotifyExamineEvidence("EVD-TORN-PAGE", &Reveal);
        G.NotifyExamineEvidence("EVD-RITE-PAPER", &Reveal);
        G.NotifyExamineEvidence("EVD-COLES-RITE", &Reveal);
        G.NotifyExamineEvidence("EVD-GWEN-GUINEA", &Reveal);

        // the optional side objective is met (its progress line reports while
        // the quest is still active - completion retires it from the snapshot)
        TLS_CHECK(ObjectiveDone(G, "OBJ-C1-SIDE"));

        // the sleep gate refuses while C1 is open
        TLS_CHECK(!G.NotifySleep(SleepReason));

        // the board - the ALTERNATIVE paths (M3.1 used dish+witness and
        // page+guinea; the three-path rule must hold from the other routes too)
        TLS_CHECK(G.BeginDialogue("DLG-CRANE-C1", Err));
        TLS_CHECK(PickChoice(G, "C01", Err));                       // formal: the sermon testimony
        TLS_CHECK(G.EvidenceCollected("EVD-CRANE-SERMON"));
        TLS_CHECK(PickChoice(G, "CH4", Err));

        G.NotifyExamineEvidence("EVD-CRANE-SERMON", &Reveal);
        G.NotifyDrawLink("EVD-LEDGER", "EVD-COLES-RITE", &Msg, &NI); // path 3 -> INS-REFUSAL
        TLS_CHECK(NI.size() == 1 && NI[0] == "INS-REFUSAL");
        G.NotifyDrawLink("EVD-RITE-PAPER", "EVD-GWEN-GUINEA", &Msg, &NI); // alt -> INS-SINLIST
        TLS_CHECK(NI.size() == 1 && NI[0] == "INS-SINLIST");
        TLS_CHECK(G.EvidenceCollected("EVD-SINLIST"));
        TLS_CHECK(G.Quests().Status("Q-M-C1") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_LEDGER_FOUND") == 1);

        // sleep -> day 2
        TLS_CHECK(G.NotifySleep(SleepReason));
        TLS_CHECK(G.CurrentDay() == 2);
        TLS_CHECK(G.GetWeather() == EWeather::Rain);
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Active);
        TLS_CHECK(G.Rumors().NpcKnows("T3-02", "RUM-NOTT-SALT"));

        // ------------------------------------------------ day 2 (C2)
        TLS_SECTION("M3.2 loop - day 2: the mill, the gates that open and close");

        // Ifor's day-1 topic is GONE (day_max 1 held both ways)
        TLS_CHECK(G.BeginDialogue("DLG-IFOR-C2", Err));
        TLS_CHECK_MSG(!ChoiceAvailable(G, "I1"), "the Trefan topic does not survive into day 2");
        TLS_CHECK(PickChoice(G, "I2", Err));
        TLS_CHECK(!G.DialogueRunning());

        // the mill scene
        G.NotifyReachArea("AREA-MILL");
        G.NotifyCollectEvidence("EVD-NOTT-BODY", "scene recorded in the sketchbook");
        G.NotifyObserveEvidence("EVD-FOOTPRINTS", &Reveal);
        G.NotifyCollectEvidence("EVD-SCALE-WEIGHTS", "secured from the scale-board");
        G.NotifyCollectEvidence("EVD-SALT-SACK", "taken from by the door");

        // the witness registration (the loop's own record for the seam test)
        {
                std::string WErr;
                TLS_CHECK(G.NotifyWitnessEvent("RUM-NOTT-SALT", 2, 9, "AREA-SQUARE", { "T3-05" }, WErr));
                const RumorKnowledge* KW = G.Rumors().NpcKnowledge("T3-05", "RUM-NOTT-SALT");
                TLS_CHECK_MSG(KW != nullptr && KW->Kind == ETestimonyKind::Direct && KW->HopCount == 0,
                        "the registered witness holds direct, first-hand knowledge");
        }

        // Coles on the fraud (day-2 topic, optional objective)
        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err));
        TLS_CHECK(PickChoice(G, "B1", Err));
        TLS_CHECK(PickChoice(G, "BH3", Err));
        TLS_CHECK(G.EvidenceCollected("EVD-COLES-FRAUD"));
        TLS_CHECK(ObjectiveDone(G, "OBJ-C2-COLES"));
        TLS_CHECK(PickChoice(G, "BH4", Err));

        // the tower-night topic is day-2 AND pattern-gated: closed before the
        // pattern exists, open after
        TLS_CHECK(G.BeginDialogue("DLG-CRANE-C1", Err));
        TLS_CHECK(PickChoice(G, "C02", Err));
        TLS_CHECK_MSG(!ChoiceAvailable(G, "CH3"),
                "the tower-night topic is shut while INS-PATTERN is unknown");
        TLS_CHECK(PickChoice(G, "CH4", Err));

        // the table, then the board's quiet verdicts
        G.NotifyExamineEvidence("EVD-NOTT-BODY", &Reveal);
        TLS_CHECK_MSG(Reveal.find("drowned in dry ground") != std::string::npos, "body examine detail");
        G.NotifyExamineEvidence("EVD-SCALE-WEIGHTS", &Reveal);
        G.NotifyExamineEvidence("EVD-SINLIST", &Reveal);
        G.NotifyExamineEvidence("EVD-COLES-FRAUD", &Reveal);
        G.NotifyExamineEvidence("EVD-SALT-SACK", &Reveal);

        // a SUPPORTING rule: consistent, but the ledger grants nothing
        G.NotifyDrawLink("EVD-SALT-SACK", "EVD-NOTT-BODY", &Msg, &NI);
        TLS_CHECK_MSG(Msg.find("Consistent") != std::string::npos, "the sack+body link holds as consistent");
        TLS_CHECK_MSG(NI.empty(), "a supporting link grants no insight");

        // a CONTRADICTION rule: folklore against weights
        G.NotifyDrawLink("EVD-CRANE-SERMON", "EVD-SCALE-WEIGHTS", &Msg, &NI);
        TLS_CHECK_MSG(Msg.find("CONTRADICTION") != std::string::npos, "sermon+weights is a contradiction");
        TLS_CHECK_MSG(NI.empty(), "a contradiction grants no insight");

        // and a plain unknown pair: the ledger keeps its silence, and the
        // no-rule verdict is still a recorded line on the board
        {
                const size_t LinksBefore = G.Evidence().Links().size();
                G.NotifyDrawLink("EVD-DISH", "EVD-LEDGER", &Msg, &NI);
                TLS_CHECK_MSG(Msg.find("silence") != std::string::npos, "unknown pair: the ledger stays silent");
                TLS_CHECK(G.Evidence().Links().size() == LinksBefore + 1);
        }

        // the pattern via the FRAUD route (M3.1 used the sinlist route)
        G.NotifyDrawLink("EVD-COLES-FRAUD", "EVD-NOTT-BODY", &Msg, &NI);
        TLS_CHECK(NI.size() == 1 && NI[0] == "INS-PATTERN");
        TLS_CHECK(G.Quests().Status("Q-M-C2a") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_CASE_OPENED") == 1);

        // the duplicate route: sinlist+body matches ANOTHER real rule, but the
        // insight is already known - the second path must not re-grant it
        {
                TLS_CHECK(G.InsightKnown("INS-PATTERN"));
                G.NotifyDrawLink("EVD-SINLIST", "EVD-NOTT-BODY", &Msg, &NI);
                TLS_CHECK_MSG(NI.empty(), "a second route to a known insight re-grants nothing");
                bool bRuleRecorded = false;
                for (const DrawnLink& L : G.Evidence().Links())
                {
                        if (L.RuleId == "LNK-SINLIST-BODY") { bRuleRecorded = true; }
                }
                TLS_CHECK(bRuleRecorded);
        }

        // the tower-night topic NOW opens (day 2 + the pattern is known)
        TLS_CHECK(G.BeginDialogue("DLG-CRANE-C1", Err));
        TLS_CHECK(PickChoice(G, "C02", Err));
        TLS_CHECK_MSG(ChoiceAvailable(G, "CH3"), "day 2 + INS-PATTERN opens the tower-night topic");
        TLS_CHECK(PickChoice(G, "CH3", Err));
        TLS_CHECK(G.GetFlag("TOP_TOWERNIGHT") == 1);
        TLS_CHECK(PickChoice(G, "CH4", Err));

        // Gwendolyn's day-2 mill topic
        TLS_CHECK(G.BeginDialogue("DLG-GWENDOLYN-C1", Err));
        TLS_CHECK(PickChoice(G, "G04", Err));
        TLS_CHECK(PickChoice(G, "H5", Err));
        TLS_CHECK(G.GetFlag("TOP_MILL2") == 1);
        TLS_CHECK(PickChoice(G, "H6", Err));

        // ------------------------------------------------ the save seam
        TLS_SECTION("M3.2 loop - the seam: witness, contradictions, no-rule lines all survive");

        const std::string S2 = G.SaveToString();
        TLS_CHECK(S2.find("\"save_version\":3") != std::string::npos);
        TLS_CHECK(static_cast<int>(G.Evidence().CollectedIds().size()) == 15);

        {
                Game* GL = MakeLoadedGame();
                TLS_CHECK(GL != nullptr);
                if (GL)
                {
                        std::string LErr;
                        TLS_CHECK_MSG(GL->LoadFromString(S2, LErr), "seam load: " + LErr);
                        TLS_CHECK(GL->Quests().Status("Q-M-C1") == EQuestStatus::Completed);
                        TLS_CHECK(GL->Quests().Status("Q-M-C2a") == EQuestStatus::Completed);
                        TLS_CHECK(GL->Quests().Status("Q-M-C3") == EQuestStatus::NotStarted);
                        TLS_CHECK(GL->GetFlag("TOP_TOWERNIGHT") == 1);
                        TLS_CHECK(GL->GetFlag("FLG_CASE_OPENED") == 1);
                        TLS_CHECK(GL->EvidenceCollected("EVD-CRANE-SERMON"));
                        TLS_CHECK(GL->InsightKnown("INS-PATTERN"));
                        // the witness record survives with its kind and provenance
                        const RumorKnowledge* KW = GL->Rumors().NpcKnowledge("T3-05", "RUM-NOTT-SALT");
                        TLS_CHECK(KW != nullptr && KW->Kind == ETestimonyKind::Direct);
                        // the board's lines survive: a contradiction, a no-rule
                        // silence, and the duplicate-route link
                        bool bContradiction = false, bNoRule = false, bDupRoute = false;
                        for (const DrawnLink& L : GL->Evidence().Links())
                        {
                                if (L.RuleId == "LNK-SERMON-WEIGHTS" && L.bContradiction) { bContradiction = true; }
                                if (L.RuleId.empty()) { bNoRule = true; }
                                if (L.RuleId == "LNK-SINLIST-BODY") { bDupRoute = true; }
                        }
                        TLS_CHECK(bContradiction);
                        TLS_CHECK(bNoRule);
                        TLS_CHECK(bDupRoute);
                        TLS_CHECK(GL->SaveToString() == S2);            // byte-stable round trip
                        delete GL;
                }
        }

        // the same session continues (load back into the running game)
        TLS_CHECK(G.LoadFromString(S2, Err));
        TLS_CHECK(G.CurrentDay() == 2);

        // the sim-RNG seam: two sessions restored from the same payload run
        // the same gossip hour and reach the same world, byte for byte
        {
                Game* GA = MakeLoadedGame();
                Game* GB = MakeLoadedGame();
                TLS_CHECK(GA != nullptr && GB != nullptr);
                if (GA && GB)
                {
                        std::string LErr;
                        TLS_CHECK(GA->LoadFromString(S2, LErr));
                        TLS_CHECK(GB->LoadFromString(S2, LErr));
                        const RumorSystem::TickResult RA = GA->TickVillageGossip(2, 9);
                        const RumorSystem::TickResult RB = GB->TickVillageGossip(2, 9);
                        TLS_CHECK(RA.NewTransmissions.size() == RB.NewTransmissions.size());
                        bool bSame = RA.NewTransmissions.size() == RB.NewTransmissions.size();
                        for (size_t I = 0; bSame && I < RA.NewTransmissions.size(); ++I)
                        {
                                const RumorTransmission& A = RA.NewTransmissions[I];
                                const RumorTransmission& B = RB.NewTransmissions[I];
                                bSame = A.RumorId == B.RumorId && A.FromNpc == B.FromNpc
                                        && A.ToNpc == B.ToNpc && A.Zone == B.Zone && A.Hour == B.Hour;
                        }
                        TLS_CHECK_MSG(bSame, "restored RNG state replays the same gossip hour");
                        TLS_CHECK(GA->SaveToString() == GB->SaveToString());
                        delete GA;
                        delete GB;
                }
        }

        // ------------------------------------------------ day 3 (C3)
        TLS_SECTION("M3.2 loop - day 3: the accusation, the method, the witness's word");

        G.AdvanceSimDay();
        TLS_CHECK(G.CurrentDay() == 3);
        TLS_CHECK(G.Quests().Status("Q-M-C3") == EQuestStatus::Active);
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);
        TLS_CHECK(G.Rumors().NpcKnows("T3-07", "RUM-SHONI-SUSPECT"));

        // the county's theory
        TLS_CHECK(G.NotifyPlayerHeardRumor("RUM-SHONI-SUSPECT", "T3-07"));
        TLS_CHECK(ObjectiveDone(G, "OBJ-C3-ACCUSATION"));
        TLS_CHECK(ObjectiveDone(G, "OBJ-SHONI-HEARD"));
        TLS_CHECK_MSG(!ObjectiveDone(G, "OBJ-SHONI-ALIBI"),
                "T3-07 knowing the ACCUSATION never satisfies the moor-road alibi");
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Active);

        // the physical method
        G.NotifyCollectEvidence("EVD-FOOTPRINTS", "recorded from the wheel-race mud");
        G.NotifyExamineEvidence("EVD-FOOTPRINTS", &Reveal);
        G.NotifyExamineEvidence("EVD-SALT-SACK", &Reveal);
        TLS_CHECK(G.Quests().Status("Q-M-C3") == EQuestStatus::Completed);
        TLS_CHECK(G.GetFlag("FLG_METHOD_SHOWN") == 1);

        // the second contradiction: folklore against human footprints
        G.NotifyExamineEvidence("EVD-COLES-HUNGER", &Reveal);
        G.NotifyDrawLink("EVD-COLES-HUNGER", "EVD-FOOTPRINTS", &Msg, &NI);
        TLS_CHECK_MSG(Msg.find("CONTRADICTION") != std::string::npos, "hunger+footprints is a contradiction");
        TLS_CHECK_MSG(NI.empty(), "no insight from the folklore contradiction");

        // the leak refuses ground outside the gossip zones
        {
                const size_t JBefore = G.Journal().size();
                TLS_CHECK(G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-MILL", Err) == -1);
                TLS_CHECK_MSG(Err.find("not a gossip zone") != std::string::npos, "non-gossip leak refused");
                TLS_CHECK(G.Journal().size() == JBefore);
                TLS_CHECK(!G.PlayerHeardRumor("RUM-SHONI-HILL"));
        }

        // THE WITNESS BRANCH of the any_of alibi: the moor-road account enters
        // the world as a REGISTERED WITNESS EVENT - a villager carries it, the
        // player never does. The quest must close through this branch alone.
        {
                std::string WErr;
                TLS_CHECK_MSG(G.NotifyWitnessEvent("RUM-SHONI-HILL", 3, 15, "AREA-SQUARE", { "T3-07" }, WErr),
                        "the moor-road account registers as witnessed");
                TLS_CHECK(G.Rumors().NpcKnows("T3-07", "RUM-SHONI-HILL"));
                TLS_CHECK_MSG(ObjectiveDone(G, "OBJ-SHONI-ALIBI"),
                        "the alibi closes through the npc_rumor branch (T3-07=RUM-SHONI-HILL)");
                TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Completed);
                TLS_CHECK(G.GetFlag("FLG_SHONI_DOUBTED") == 1);
                TLS_CHECK(G.GetFlag("FLG_SHONI_TAKEN") == 0);
                TLS_CHECK_MSG(!G.PlayerHeardRumor("RUM-SHONI-HILL"),
                        "the witness carried the word - the player never heard the alibi");
        }

        // the two shoni rumors pull against each other: conflict detection
        {
                bool bFound = false;
                for (const RumorSystem::RumorConflict& C : G.Rumors().FindConflicts("T3-07"))
                {
                        if ((C.RumorA == "RUM-SHONI-SUSPECT" && C.RumorB == "RUM-SHONI-HILL")
                                || (C.RumorA == "RUM-SHONI-HILL" && C.RumorB == "RUM-SHONI-SUSPECT"))
                        {
                                bFound = C.Topic == "shoni";
                        }
                }
                TLS_CHECK_MSG(bFound, "T3-07 holds both shoni rumors - the conflict is found by topic");
        }

        // the day-3 word travels inside the zones only
        for (int Hour = 16; Hour <= 21; ++Hour)
        {
                const RumorSystem::TickResult Res = G.TickVillageGossip(3, Hour);
                for (const RumorTransmission& T : Res.NewTransmissions)
                {
                        TLS_CHECK_MSG(G.Rumors().IsGossipZone(T.Zone), "day-3 transmissions stay in gossip zones");
                }
        }

        // the loop's final state: every piece of the slice's evidence is in
        // the sketchbook, and the world saves
        TLS_CHECK(static_cast<int>(G.Evidence().CollectedIds().size()) == 16);
        const std::string S3 = G.SaveToString();
        TLS_CHECK(!S3.empty());
}

// ------------------------------------------------- the multi-day decay watch

void RunDecayWatch(Game& G)
{
        TLS_SECTION("M3.2 decay watch - the leaked word dies, the witness remembers on the curve");

        std::string Err, WErr;

        // the WITNESSED curve: the mill discovery is born on day 2 with the
        // finder as a first-hand source (origin_confidence 1.0, decay 0.1)
        G.NewGame();
        G.AdvanceSimDay();
        TLS_CHECK(G.CurrentDay() == 2);
        TLS_CHECK(G.NotifyWitnessEvent("RUM-NOTT-SALT", 2, 9, "AREA-SQUARE", { "T3-05" }, WErr));
        const RumorDef* SaltDef = G.Rumors().FindDef("RUM-NOTT-SALT");
        TLS_CHECK(SaltDef != nullptr);
        const double SaltOrigin = SaltDef ? SaltDef->OriginConfidence : 1.0;
        TLS_CHECK_MSG(SaltOrigin == 1.0, "the mill account is born first-hand");
        const double SaltFactor = 1.0 - (SaltDef ? SaltDef->Decay : 0.1);   // 0.9 per day

        // the LEAKED word: the moor-road account enters anonymously on day 3
        G.AdvanceSimDay();
        TLS_CHECK(G.CurrentDay() == 3);
        TLS_CHECK(G.NotifyPlayerLeakRumor("RUM-SHONI-HILL", "AREA-SQUARE", Err) > 0);
        TLS_CHECK(G.PlayerHeardRumor("RUM-SHONI-HILL"));

        const RumorDef* HillDef = G.Rumors().FindDef("RUM-SHONI-HILL");
        TLS_CHECK(HillDef != nullptr);
        const double HillOrigin = HillDef ? HillDef->OriginConfidence : 0.55;
        const double HillFactor = 1.0 - (HillDef ? HillDef->Decay : 0.25);  // 0.75 per day
        const double Forget = G.Rumors().GetRules().ForgetBelow;            // 0.15

        // capture one LEAKED holder (anonymous word: hop 1, capped confidence)
        std::string LeakedKnower;
        for (const std::string& Knower : G.Rumors().NpcsKnowing("RUM-SHONI-HILL"))
        {
                const RumorKnowledge* K = G.Rumors().NpcKnowledge(Knower, "RUM-SHONI-HILL");
                if (K && K->FromNpc == "PLAYER" && K->HopCount == 1 && K->Confidence == 0.55)
                {
                        LeakedKnower = Knower;
                        break;
                }
        }
        TLS_CHECK_MSG(!LeakedKnower.empty(), "the leak produced a hop-1 holder at the capped confidence");

        // the witnessed curve, day by day - exact multiplication, no drift
        // (the day-3 decay already ran when the session entered day 3)
        double ExpectedSalt = SaltOrigin * SaltFactor;
        for (int Day = 4; Day <= 8; ++Day)
        {
                G.AdvanceSimDay();
                TLS_CHECK(G.CurrentDay() == Day);
                ExpectedSalt *= SaltFactor;

                const RumorKnowledge* W = G.Rumors().NpcKnowledge("T3-05", "RUM-NOTT-SALT");
                TLS_CHECK_MSG(W != nullptr, "the direct witness holds the mill account all week");
                if (W)
                {
                        char Got[32], Want[32];
                        std::snprintf(Got, sizeof(Got), "%.6f", W->Confidence);
                        std::snprintf(Want, sizeof(Want), "%.6f", ExpectedSalt);
                        TLS_CHECK_MSG(std::string(Got) == Want,
                                "day " + std::to_string(Day) + ": witness confidence follows the decay curve exactly");
                }

                int NewKnowers = 0;
                for (int Hour : { 9, 12, 18 })
                {
                        const RumorSystem::TickResult Res = G.TickVillageGossip(Day, Hour);
                        NewKnowers += Res.NewKnowersToday;
                        for (const RumorTransmission& T : Res.NewTransmissions)
                        {
                                TLS_CHECK_MSG(G.Rumors().IsGossipZone(T.Zone),
                                        "decay-watch transmissions stay in gossip zones");
                        }
                }
                TLS_CHECK_MSG(NewKnowers <= 5, "the 30% daily cap holds through the watch");
        }

        // day 8 is reached: the fifth decay of the moor-road word - the data
        // decides the day it dies (0.55 x 0.75^5 = 0.131 < 0.15), not the mood
        {
                int ForgetDay = -1;
                double C = HillOrigin;
                for (int D = 1; D <= 12; ++D)
                {
                        C *= HillFactor;
                        if (C < Forget) { ForgetDay = 3 + D; break; }
                }
                TLS_CHECK_MSG(ForgetDay == 8, "the slice data forgets the leaked word on day 8");
        }
        {
                const RumorKnowledge* W = G.Rumors().NpcKnowledge("T3-05", "RUM-NOTT-SALT");
                TLS_CHECK_MSG(W != nullptr, "the witnessed mill account outlives the leaked word");
                if (W)
                {
                        char Got[32], Want[32];
                        std::snprintf(Got, sizeof(Got), "%.6f", W->Confidence);
                        std::snprintf(Want, sizeof(Want), "%.6f", ExpectedSalt);
                        TLS_CHECK_MSG(std::string(Got) == Want, "day 8: the witnessed curve is still exact");
                }
        }
        TLS_CHECK_MSG(G.Rumors().NpcKnowledge(LeakedKnower, "RUM-SHONI-HILL") == nullptr,
                "the leaked word fades from its day-3 holder exactly when the data says");

        // and the village keeps talking inside its zones after the erasure
        for (int Hour : { 9, 12, 18 })
        {
                const RumorSystem::TickResult Res = G.TickVillageGossip(8, Hour);
                for (const RumorTransmission& T : Res.NewTransmissions)
                {
                        TLS_CHECK_MSG(G.Rumors().IsGossipZone(T.Zone), "day-8 transmissions stay in gossip zones");
                }
        }
}

// ------------------------------------------------------- order independence

void TestOrderIndependence(Game& GA, Game& GB)
{
        TLS_SECTION("M3.2 order independence - one day-1 set, two orders, one truth");

        std::string Err;

        // ORDER A: interrogations first, ground evidence after, board last
        {
                Game& G = GA;
                G.NewGame();
                G.NotifyReachArea("AREA-CHURCHYARD");
                G.NotifyObserveEvidence("EVD-GRAVE");
                G.NotifyCollectEvidence("EVD-GRAVE", "register");
                G.BeginDialogue("DLG-IFOR-C2", Err);
                PickChoice(G, "I1", Err);
                G.BeginDialogue("DLG-COLES-C1", Err);
                PickChoice(G, "B1", Err);
                PickChoice(G, "BH1", Err);
                PickChoice(G, "BH4", Err);
                G.BeginDialogue("DLG-MAIR-C1", Err);
                PickChoice(G, "M1", Err);
                G.BeginDialogue("DLG-CRANE-C1", Err);
                PickChoice(G, "C01", Err);
                PickChoice(G, "CH4", Err);
                G.NotifyReachArea("AREA-BOUNDARY");
                G.NotifyCollectEvidence("EVD-DISH", "dish");
                G.NotifyReachArea("AREA-COTTAGE");
                G.NotifyCollectEvidence("EVD-LEDGER", "ledger");
                G.NotifyCollectEvidence("EVD-RITE-PAPER", "rite paper");
                G.NotifyCollectEvidence("EVD-TORN-PAGE", "torn page");
                G.BeginDialogue("DLG-GWENDOLYN-C1", Err);
                PickChoice(G, "G04", Err);
                PickChoice(G, "H1", Err);
                PickChoice(G, "H2", Err);
                PickChoice(G, "H6", Err);
                G.NotifyRestorePage("EVD-TORN-PAGE");
                for (const char* Ev : { "EVD-DISH", "EVD-LEDGER", "EVD-TORN-PAGE", "EVD-COLES-RITE", "EVD-GWEN-GUINEA" })
                {
                        G.NotifyExamineEvidence(Ev);
                }
                std::vector<std::string> NI;
                G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE", nullptr, &NI);
                G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-GWEN-GUINEA", nullptr, &NI);
        }

        // ORDER B: ground evidence first, the Black Ram before Coles, the
        // examinations interleaved - the same interaction SET, another ORDER
        {
                Game& G = GB;
                G.NewGame();
                G.NotifyReachArea("AREA-BOUNDARY");
                G.NotifyCollectEvidence("EVD-DISH", "dish");
                G.NotifyReachArea("AREA-COTTAGE");
                G.NotifyCollectEvidence("EVD-LEDGER", "ledger");
                G.NotifyCollectEvidence("EVD-RITE-PAPER", "rite paper");
                G.NotifyCollectEvidence("EVD-TORN-PAGE", "torn page");
                G.NotifyRestorePage("EVD-TORN-PAGE");
                G.NotifyExamineEvidence("EVD-TORN-PAGE");
                G.NotifyReachArea("AREA-CHURCHYARD");
                G.NotifyObserveEvidence("EVD-GRAVE");
                G.NotifyCollectEvidence("EVD-GRAVE", "register");
                G.BeginDialogue("DLG-IFOR-C2", Err);
                PickChoice(G, "I1", Err);
                G.BeginDialogue("DLG-GWENDOLYN-C1", Err);
                PickChoice(G, "G04", Err);
                PickChoice(G, "H1", Err);
                PickChoice(G, "H2", Err);
                PickChoice(G, "H6", Err);
                G.NotifyExamineEvidence("EVD-DISH");
                G.NotifyExamineEvidence("EVD-GWEN-GUINEA");
                G.BeginDialogue("DLG-MAIR-C1", Err);
                PickChoice(G, "M1", Err);
                G.BeginDialogue("DLG-CRANE-C1", Err);
                PickChoice(G, "C01", Err);
                PickChoice(G, "CH4", Err);
                G.BeginDialogue("DLG-COLES-C1", Err);
                PickChoice(G, "B1", Err);
                PickChoice(G, "BH1", Err);
                PickChoice(G, "BH4", Err);
                G.NotifyExamineEvidence("EVD-LEDGER");
                G.NotifyExamineEvidence("EVD-COLES-RITE");
                std::vector<std::string> NI;
                G.NotifyDrawLink("EVD-TORN-PAGE", "EVD-GWEN-GUINEA", nullptr, &NI);
                G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE", nullptr, &NI);
        }

        // the same set, two orders, one canonical state
        TLS_CHECK(GA.Quests().Status("Q-M-C1") == EQuestStatus::Completed);
        TLS_CHECK(GB.Quests().Status("Q-M-C1") == EQuestStatus::Completed);
        TLS_CHECK_MSG(CanonicalSignature(GA) == CanonicalSignature(GB),
                "the day-1 interaction set lands on the same canonical state in both orders");

        // the journals legitimately differ in ORDER (they follow the player)
        TLS_CHECK_MSG(GA.Journal().size() == GB.Journal().size(),
                "both journals recorded the same number of events");
        // trust math is additive: the same deltas were applied in both orders
        TLS_CHECK(GA.GetTrust("CHR-03") == GB.GetTrust("CHR-03"));
        TLS_CHECK(GA.GetTrust("CHR-06") == GB.GetTrust("CHR-06"));
        TLS_CHECK(GA.GetTrust("CHR-13") == GB.GetTrust("CHR-13"));
}

// -------------------------------------------- save / restore expansion (3b)

void TestSaveRestoreExpansion(Game& G)
{
        TLS_SECTION("M3.2 save/restore - multi-cycle, ghosts, empties, dialogue, RNG");

        std::string Err;

        // a rich mid-loop state: day 2, gossip history, a drawn board, flags
        G.NewGame();
        G.NotifyReachArea("AREA-CHURCHYARD");
        G.NotifyObserveEvidence("EVD-GRAVE");
        G.NotifyCollectEvidence("EVD-DISH", "x");
        G.NotifyExamineEvidence("EVD-DISH");
        G.NotifyCollectEvidence("EVD-COLES-RITE", "x");
        G.NotifyExamineEvidence("EVD-COLES-RITE");
        G.NotifyDrawLink("EVD-DISH", "EVD-COLES-RITE");
        G.TickVillageGossip(1, 9);
        G.TickVillageGossip(1, 12);
        G.NotifyPlayerHeardRumor("RUM-HUNGER-RETURNS", "T3-06");
        G.BeginDialogue("DLG-COLES-C1", Err);                       // left RUNNING on purpose
        const std::string Rich = G.SaveToString();

        // 1) save -> load -> resave, THREE cycles, byte-identical every time
        {
                std::string Payload = Rich;
                for (int Cycle = 1; Cycle <= 3; ++Cycle)
                {
                        Game* GL = MakeLoadedGame();
                        TLS_CHECK(GL != nullptr);
                        if (!GL) { break; }
                        TLS_CHECK_MSG(GL->LoadFromString(Payload, Err), "cycle load: " + Err);
                        const std::string Resaved = GL->SaveToString();
                        TLS_CHECK_MSG(Resaved == Payload, "save->load->resave cycle " + std::to_string(Cycle) + " is byte-identical");
                        Payload = Resaved;
                        delete GL;
                }
        }

        // 2) ghost ids are REFUSED - and the running session stays untouched
        {
                // baseline session distinct from the payload world
                G.NewGame();
                G.NotifyCollectEvidence("EVD-LEDGER", "session marker");
                G.TickVillageGossip(1, 8);
                const std::string Session = G.SaveToString();

                std::string Attack;
                TLS_CHECK(InjectIntoArray(Rich, "evidence", "{\"id\":\"EVD-GHOST\",\"collected\":true},", Attack));
                TLS_CHECK(!G.LoadFromString(Attack, Err));
                TLS_CHECK_MSG(Err.find("unknown evidence") != std::string::npos, "ghost evidence named");
                TLS_CHECK_MSG(G.SaveToString() == Session, "ghost-evidence refusal leaves the session untouched");

                TLS_CHECK(InjectIntoArray(Rich, "quests", "{\"id\":\"Q-GHOST\",\"status\":\"completed\"},", Attack));
                TLS_CHECK(!G.LoadFromString(Attack, Err));
                TLS_CHECK_MSG(Err.find("unknown quest") != std::string::npos, "ghost quest named");
                TLS_CHECK(G.SaveToString() == Session);

                TLS_CHECK(ReplaceSectionValue(Rich, "status", "\"ghosted\"", Attack));
                TLS_CHECK(!G.LoadFromString(Attack, Err));
                TLS_CHECK_MSG(Err.find("unknown quest status") != std::string::npos, "bad status string named");
                TLS_CHECK(G.SaveToString() == Session);

                TLS_CHECK(InjectIntoArray(Rich, "insights_known", "\"INS-GHOST\",", Attack));
                TLS_CHECK(!G.LoadFromString(Attack, Err));
                TLS_CHECK_MSG(Err.find("unknown insight") != std::string::npos, "ghost insight named");
                TLS_CHECK(G.SaveToString() == Session);

                TLS_CHECK(ReplaceSectionValue(Rich, "rule", "\"LNK-GHOST\"", Attack));
                TLS_CHECK(!G.LoadFromString(Attack, Err));
                TLS_CHECK_MSG(Err.find("unknown rule") != std::string::npos, "ghost link rule named");
                TLS_CHECK(G.SaveToString() == Session);

                TLS_CHECK(ReplaceSectionValue(Rich, "chain", "[2]", Attack));
                TLS_CHECK(!G.LoadFromString(Attack, Err));
                TLS_CHECK_MSG(Err.find("not a string") != std::string::npos, "non-string custody entry named");
                TLS_CHECK(G.SaveToString() == Session);

                // control: the uncorrupted payload still loads
                TLS_CHECK(G.LoadFromString(Rich, Err));
        }

        // 3) unknown REACHED AREAS are tolerated by contract - inert, and
        //    they round-trip (no content can reference a non-existent area)
        {
                std::string WithGhostArea;
                TLS_CHECK(AppendIntoArray(Rich, "reached_areas", ",\"AREA-GHOST\"", WithGhostArea));
                Game* GL = MakeLoadedGame();
                TLS_CHECK(GL != nullptr);
                if (GL)
                {
                        TLS_CHECK(GL->LoadFromString(WithGhostArea, Err));
                        TLS_CHECK(GL->HasReachedArea("AREA-GHOST"));
                        TLS_CHECK(GL->Quests().Status("Q-M-C1") == EQuestStatus::Active);
                        TLS_CHECK_MSG(GL->SaveToString() == WithGhostArea, "the ghost area round-trips");
                        delete GL;
                }
        }

        // 4) EMPTY vs ABSENT optional sections: no unintended difference
        {
                const char* OptionalKeys[] = { "flags", "reached_areas", "dialogue_history", "journal" };
                for (const char* Key : OptionalKeys)
                {
                        std::string Absent, Emptied;
                        TLS_CHECK(RemoveSection(Rich, Key, Absent));
                        // journal and reached_areas are arrays; the rest are objects
                        const std::string EmptyVal =
                                (std::string(Key) == "journal" || std::string(Key) == "reached_areas") ? "[]" : "{}";
                        TLS_CHECK(ReplaceSectionValue(Rich, Key, EmptyVal.c_str(), Emptied));
                        Game* GA = MakeLoadedGame();
                        Game* GB = MakeLoadedGame();
                        TLS_CHECK(GA != nullptr && GB != nullptr);
                        if (GA && GB)
                        {
                                TLS_CHECK(GA->LoadFromString(Absent, Err));
                                TLS_CHECK(GB->LoadFromString(Emptied, Err));
                                TLS_CHECK_MSG(GA->SaveToString() == GB->SaveToString(),
                                        std::string(Key) + ": absent and empty produce the same world");
                        }
                        delete GA;
                        delete GB;
                }

                // the four REQUIRED v2 sections may not vanish
                for (const char* Key : { "village", "evidence", "quests", "rumors" })
                {
                        std::string Absent;
                        TLS_CHECK(RemoveSection(Rich, Key, Absent));
                        TLS_CHECK(!G.LoadFromString(Absent, Err));
                }
        }

        // 5) a load while a dialogue is running: the save happens at the desk -
        //    the interrupted session is not part of the state, and a VALID
        //    load replaces the world cleanly
        {
                Game* GAlt = MakeLoadedGame();
                TLS_CHECK(GAlt != nullptr);
                if (GAlt)
                {
                        GAlt->NewGame();
                        GAlt->AdvanceSimDay();
                        const std::string Alt = GAlt->SaveToString();
                        delete GAlt;

                        TLS_CHECK(G.BeginDialogue("DLG-COLES-C1", Err)); // a session is open at load time
                        TLS_CHECK(G.DialogueRunning());
                        TLS_CHECK(G.LoadFromString(Alt, Err));
                        TLS_CHECK_MSG(!G.DialogueRunning(), "no dialogue survives a load - saves happen at the desk");
                        TLS_CHECK(G.CurrentDay() == 2);
                        TLS_CHECK(G.GetWeather() == EWeather::Rain);
                }
        }

        // 6) the RNG seam, standalone: identical restored states tick alike
        {
                Game* GA = MakeLoadedGame();
                Game* GB = MakeLoadedGame();
                TLS_CHECK(GA != nullptr && GB != nullptr);
                if (GA && GB)
                {
                        TLS_CHECK(GA->LoadFromString(Rich, Err));
                        TLS_CHECK(GB->LoadFromString(Rich, Err));
                        GA->TickVillageGossip(1, 13);
                        GB->TickVillageGossip(1, 13);
                        TLS_CHECK_MSG(GA->SaveToString() == GB->SaveToString(),
                                "two restored sessions replay hour 13 identically");
                        delete GA;
                        delete GB;
                }
        }
}

// --------------------------------- a failed urgent quest is never resurrected

void TestFailureNoResurrection(Game& G)
{
        TLS_SECTION("M3.2 regression - expiry failure cannot be undone by later knowledge");

        std::string Err, WErr;
        G.NewGame();
        G.AdvanceSimDay();
        G.AdvanceSimDay();                                          // day 3: the window is open
        G.AdvanceSimDay();                                          // day 4: it closes
        TLS_CHECK(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Failed);
        TLS_CHECK(G.GetFlag("FLG_SHONI_TAKEN") == 1);

        // NOW the moor-road account reaches T3-07 - too late
        TLS_CHECK(G.NotifyWitnessEvent("RUM-SHONI-HILL", 4, 12, "AREA-SQUARE", { "T3-07" }, WErr));
        TLS_CHECK(G.Rumors().NpcKnows("T3-07", "RUM-SHONI-HILL"));
        TLS_CHECK_MSG(G.Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Failed,
                "knowledge arriving after expiry never resurrects the quest");
        TLS_CHECK(G.GetFlag("FLG_SHONI_DOUBTED") == 0);

        // and the failed state survives the seam
        const std::string S = G.SaveToString();
        Game* GL = MakeLoadedGame();
        TLS_CHECK(GL != nullptr);
        if (GL)
        {
                TLS_CHECK(GL->LoadFromString(S, Err));
                TLS_CHECK(GL->Quests().Status("Q-S-C3-SHONI") == EQuestStatus::Failed);
                TLS_CHECK(GL->GetFlag("FLG_SHONI_TAKEN") == 1);
                TLS_CHECK(GL->SaveToString() == S);
                delete GL;
        }
}

// ------------------------------------------------------------------- entry

void RunAll()
{
        {
                // the extended loop, twice, from the same default seed - the
                // whole thing (including its internal seams) is deterministic
                Game* GA = MakeLoadedGame();
                Game* GB = MakeLoadedGame();
                TLS_CHECK(GA != nullptr && GB != nullptr);
                if (GA && GB)
                {
                        RunExtendedLoop(*GA);
                        RunExtendedLoop(*GB);
                        TLS_CHECK_MSG(GA->SaveToString() == GB->SaveToString(),
                                "same-seed replay of the extended loop is byte-identical");
                }
                delete GA;
                delete GB;
        }

        {
                Game* G = MakeLoadedGame();
                if (G) { RunDecayWatch(*G); delete G; }
        }

        {
                Game* GA = MakeLoadedGame();
                Game* GB = MakeLoadedGame();
                TLS_CHECK(GA != nullptr && GB != nullptr);
                if (GA && GB)
                {
                        TestOrderIndependence(*GA, *GB);
                }
                delete GA;
                delete GB;
        }

        {
                Game* G = MakeLoadedGame();
                if (G) { TestSaveRestoreExpansion(*G); delete G; }
                G = MakeLoadedGame();
                if (G) { TestFailureNoResurrection(*G); delete G; }
        }
}

} // namespace tls_test_m32
