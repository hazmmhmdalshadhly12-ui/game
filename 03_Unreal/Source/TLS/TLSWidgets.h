// THE LAST SIN: The Sin-Eater - M1
// TLSWidgets: the four slice UI panels, constructed entirely in C++
// (WidgetTree->ConstructWidget - no .uasset UI files, consistent with the
// code-only project approach used since M0).
// Panels are display-only; selection input is routed by the character /
// game mode (number keys), which keeps the widgets simple and testable.
// The engraved look (TLS-UI-001..004) is the M1 art-pass target; colours
// already follow the GAME_BIBLE 7.2 palette.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "TLSWidgets.generated.h"

class UTextBlock;
class UVerticalBox;
class UCanvasPanel;

/** HUD: day/time/weather line, current objective, interaction prompt. */
UCLASS()
class TLS_API UTLSHUDWidget : public UUserWidget
{
        GENERATED_BODY()

public:
        void SetStatusLine(const FString& Line);
        void SetObjectiveLine(const FString& Line);
        void SetPrompt(const FString& Line);
        void SetToast(const FString& Line);

protected:
        virtual void NativeConstruct() override;

        UPROPERTY(Transient)
        UTextBlock* StatusText;

        UPROPERTY(Transient)
        UTextBlock* ObjectiveText;

        UPROPERTY(Transient)
        UTextBlock* PromptText;

        UPROPERTY(Transient)
        UTextBlock* ToastText;
};

/** Dialogue: speaker name, body text, numbered choices. */
UCLASS()
class TLS_API UTLSDialogueWidget : public UUserWidget
{
        GENERATED_BODY()

public:
        void SetDialogue(const FString& Speaker, const FString& Text, const TArray<FString>& Choices);
        void SetFinished();

protected:
        virtual void NativeConstruct() override;

        UPROPERTY(Transient)
        UTextBlock* SpeakerText;

        UPROPERTY(Transient)
        UTextBlock* BodyText;

        UPROPERTY(Transient)
        UVerticalBox* ChoicesBox;
};

/** Ledger board: collected evidence, drawn links, insights, verdict line. */
UCLASS()
class TLS_API UTLSLedgerWidget : public UUserWidget
{
        GENERATED_BODY()

public:
        void SetLedger(const TArray<FString>& EvidenceLines, const TArray<FString>& LinkLines,
                const TArray<FString>& InsightLines, const FString& VerdictLine);

protected:
        virtual void NativeConstruct() override;

        UPROPERTY(Transient)
        UTextBlock* EvidenceText;

        UPROPERTY(Transient)
        UTextBlock* LinksText;

        UPROPERTY(Transient)
        UTextBlock* InsightsText;

        UPROPERTY(Transient)
        UTextBlock* VerdictText;
};

/** Journal: quests + objectives + Edmund's diary entries. */
UCLASS()
class TLS_API UTLSJournalWidget : public UUserWidget
{
        GENERATED_BODY()

public:
        void SetJournal(const TArray<FString>& QuestLines, const TArray<FString>& DiaryLines);

protected:
        virtual void NativeConstruct() override;

        UPROPERTY(Transient)
        UTextBlock* QuestsText;

        UPROPERTY(Transient)
        UTextBlock* DiaryText;
};
