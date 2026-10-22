// THE LAST SIN: The Sin-Eater - M1
// TLSWidgets.cpp - code-built UMG panels.

#include "TLSWidgets.h"

#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "WidgetTree.h"

namespace TLSUI
{
        // GAME_BIBLE 7.2 palette
        const FLinearColor Paper()    { return FLinearColor::FromSRGBColor(FColor::FromHex("D9CBB2")); }
        const FLinearColor Ink()      { return FLinearColor::FromSRGBColor(FColor::FromHex("1C2226")); }
        const FLinearColor Slate()    { return FLinearColor::FromSRGBColor(FColor::FromHex("3A4550")); }
        const FLinearColor Candle()   { return FLinearColor::FromSRGBColor(FColor::FromHex("E8A34D")); }
        const FLinearColor SinBlue()  { return FLinearColor::FromSRGBColor(FColor::FromHex("7FA8C9")); }

        UTextBlock* MakeText(UWidgetTree* Tree, const FLinearColor& Color, int32 Size, bool bShadow = true)
        {
                UTextBlock* Text = Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
                Text->SetColorAndOpacity(FSlateColor(Color));
                if (bShadow)
                {
                        FTextBlockStyle Style = Text->GetTextBlockStyle();
                        Style.SetShadowOffset(FVector2D(1.0f, 1.0f));
                        Style.SetShadowColorAndOpacity(FLinearColor(0.0f, 0.0f, 0.0f, 0.85f));
                        Text->SetTextBlockStyle(Style);
                }
                Text->SetAutoWrapText(true);
                FSlateFontInfo Font = Text->GetFont();
                Font.Size = Size;
                Text->SetFont(Font);
                return Text;
        }

        UCanvasPanelSlot* PlaceOnCanvas(UCanvasPanel* Canvas, UWidget* Widget,
                const FAnchors& Anchors, const FVector2D& Offset, const FVector2D& Size)
        {
                UCanvasPanelSlot* Slot = Canvas->AddChildToCanvas(Widget);
                Slot->SetAnchors(Anchors);
                Slot->SetPosition(Offset);
                Slot->SetSize(Size);
                return Slot;
        }
}

// ---------------------------------------------------------------- HUD

void UTLSHUDWidget::NativeConstruct()
{
        Super::NativeConstruct();

        UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
        WidgetTree->RootWidget = Canvas;

        StatusText = TLSUI::MakeText(WidgetTree, TLSUI::Paper(), 20);
        TLSUI::PlaceOnCanvas(Canvas, StatusText, FAnchors(0.0f, 0.0f), FVector2D(24.0f, 20.0f), FVector2D(700.0f, 30.0f));

        ObjectiveText = TLSUI::MakeText(WidgetTree, TLSUI::Candle(), 16);
        TLSUI::PlaceOnCanvas(Canvas, ObjectiveText, FAnchors(0.0f, 1.0f), FVector2D(24.0f, -120.0f), FVector2D(900.0f, 90.0f));

        PromptText = TLSUI::MakeText(WidgetTree, TLSUI::Candle(), 22);
        TLSUI::PlaceOnCanvas(Canvas, PromptText, FAnchors(0.5f, 1.0f), FVector2D(-350.0f, -70.0f), FVector2D(700.0f, 34.0f));

        ToastText = TLSUI::MakeText(WidgetTree, TLSUI::SinBlue(), 17);
        TLSUI::PlaceOnCanvas(Canvas, ToastText, FAnchors(0.5f, 0.0f), FVector2D(-450.0f, 60.0f), FVector2D(900.0f, 60.0f));
        ToastText->SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UTLSHUDWidget::SetStatusLine(const FString& Line)
{
        if (StatusText) { StatusText->SetText(FText::FromString(Line)); }
}

void UTLSHUDWidget::SetObjectiveLine(const FString& Line)
{
        if (ObjectiveText) { ObjectiveText->SetText(FText::FromString(Line)); }
}

void UTLSHUDWidget::SetPrompt(const FString& Line)
{
        if (PromptText) { PromptText->SetText(FText::FromString(Line)); }
}

void UTLSHUDWidget::SetToast(const FString& Line)
{
        if (ToastText) { ToastText->SetText(FText::FromString(Line)); }
}

// ---------------------------------------------------------------- Dialogue

void UTLSDialogueWidget::NativeConstruct()
{
        Super::NativeConstruct();

        UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
        WidgetTree->RootWidget = Canvas;

        UVerticalBox* Panel = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        UCanvasPanelSlot* PanelSlot = TLSUI::PlaceOnCanvas(Canvas, Panel,
                FAnchors(0.5f, 1.0f), FVector2D(-480.0f, -330.0f), FVector2D(960.0f, 310.0f));

        SpeakerText = TLSUI::MakeText(WidgetTree, TLSUI::Candle(), 19);
        UVerticalBoxSlot* SpeakerSlot = Panel->AddChildToVerticalBox(SpeakerText);
        SpeakerSlot->SetPadding(FMargin(10.0f, 6.0f, 10.0f, 2.0f));

        BodyText = TLSUI::MakeText(WidgetTree, TLSUI::Paper(), 17);
        UVerticalBoxSlot* BodySlot = Panel->AddChildToVerticalBox(BodyText);
        BodySlot->SetPadding(FMargin(10.0f, 2.0f, 10.0f, 8.0f));

        ChoicesBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        UVerticalBoxSlot* ChoicesSlot = Panel->AddChildToVerticalBox(ChoicesBox);
        ChoicesSlot->SetPadding(FMargin(10.0f, 2.0f, 10.0f, 8.0f));
}

void UTLSDialogueWidget::SetDialogue(const FString& Speaker, const FString& Text, const TArray<FString>& Choices)
{
        if (SpeakerText) { SpeakerText->SetText(FText::FromString(Speaker)); }
        if (BodyText) { BodyText->SetText(FText::FromString(Text)); }

        if (ChoicesBox)
        {
                ChoicesBox->ClearChildren();
                for (int32 I = 0; I < Choices.Num(); ++I)
                {
                        UTextBlock* ChoiceText = TLSUI::MakeText(WidgetTree, TLSUI::SinBlue(), 16);
                        ChoiceText->SetText(FText::FromString(FString::Printf(TEXT("%d.  %s"), I + 1, *Choices[I])));
                        ChoicesBox->AddChildToVerticalBox(ChoiceText);
                }
        }
}

void UTLSDialogueWidget::SetFinished()
{
        if (SpeakerText) { SpeakerText->SetText(FText::FromString(TEXT(""))); }
        if (BodyText) { BodyText->SetText(FText::FromString(TEXT(""))); }
        if (ChoicesBox) { ChoicesBox->ClearChildren(); }
}

// ---------------------------------------------------------------- Ledger board

void UTLSLedgerWidget::NativeConstruct()
{
        Super::NativeConstruct();

        UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
        WidgetTree->RootWidget = Canvas;

        UVerticalBox* Panel = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        TLSUI::PlaceOnCanvas(Canvas, Panel, FAnchors(0.5f, 0.5f), FVector2D(-500.0f, -300.0f), FVector2D(1000.0f, 600.0f));

        EvidenceText = TLSUI::MakeText(WidgetTree, TLSUI::Paper(), 15);
        UVerticalBoxSlot* EvSlot = Panel->AddChildToVerticalBox(EvidenceText);
        EvSlot->SetPadding(FMargin(10.0f, 8.0f, 10.0f, 6.0f));

        LinksText = TLSUI::MakeText(WidgetTree, TLSUI::SinBlue(), 15);
        UVerticalBoxSlot* LinkSlot = Panel->AddChildToVerticalBox(LinksText);
        LinkSlot->SetPadding(FMargin(10.0f, 2.0f, 10.0f, 6.0f));

        InsightsText = TLSUI::MakeText(WidgetTree, TLSUI::Candle(), 17);
        UVerticalBoxSlot* InsightSlot = Panel->AddChildToVerticalBox(InsightsText);
        InsightSlot->SetPadding(FMargin(10.0f, 2.0f, 10.0f, 6.0f));

        VerdictText = TLSUI::MakeText(WidgetTree, TLSUI::Paper(), 16);
        UVerticalBoxSlot* VerdictSlot = Panel->AddChildToVerticalBox(VerdictText);
        VerdictSlot->SetPadding(FMargin(10.0f, 6.0f, 10.0f, 8.0f));
}

void UTLSLedgerWidget::SetLedger(const TArray<FString>& EvidenceLines, const TArray<FString>& LinkLines,
        const TArray<FString>& InsightLines, const FString& VerdictLine)
{
        if (EvidenceText)
        {
                EvidenceText->SetText(FText::FromString(FString::Join(EvidenceLines, TEXT("\n"))));
        }
        if (LinksText)
        {
                LinksText->SetText(FText::FromString(FString::Join(LinkLines, TEXT("\n"))));
        }
        if (InsightsText)
        {
                InsightsText->SetText(FText::FromString(FString::Join(InsightLines, TEXT("\n"))));
        }
        if (VerdictText)
        {
                VerdictText->SetText(FText::FromString(VerdictLine));
        }
}

// ---------------------------------------------------------------- Journal

void UTLSJournalWidget::NativeConstruct()
{
        Super::NativeConstruct();

        UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass());
        WidgetTree->RootWidget = Canvas;

        UVerticalBox* Panel = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
        TLSUI::PlaceOnCanvas(Canvas, Panel, FAnchors(0.5f, 0.5f), FVector2D(-470.0f, -320.0f), FVector2D(940.0f, 640.0f));

        QuestsText = TLSUI::MakeText(WidgetTree, TLSUI::Paper(), 16);
        UVerticalBoxSlot* QuestSlot = Panel->AddChildToVerticalBox(QuestsText);
        QuestSlot->SetPadding(FMargin(12.0f, 10.0f, 12.0f, 10.0f));

        DiaryText = TLSUI::MakeText(WidgetTree, TLSUI::SinBlue(), 15);
        UVerticalBoxSlot* DiarySlot = Panel->AddChildToVerticalBox(DiaryText);
        DiarySlot->SetPadding(FMargin(12.0f, 4.0f, 12.0f, 12.0f));
}

void UTLSJournalWidget::SetJournal(const TArray<FString>& QuestLines, const TArray<FString>& DiaryLines)
{
        if (QuestsText)
        {
                QuestsText->SetText(FText::FromString(FString::Join(QuestLines, TEXT("\n"))));
        }
        if (DiaryText)
        {
                DiaryText->SetText(FText::FromString(FString::Join(DiaryLines, TEXT("\n"))));
        }
}
