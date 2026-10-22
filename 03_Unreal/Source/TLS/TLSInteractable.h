// THE LAST SIN: The Sin-Eater - M1
// TLSInteractable: world interaction point - evidence pickups, observation
// spots, the examination table, the ledger board, the writing desk (save)
// and the bed (sleep). Spawns only on its narrative day; interaction is
// routed to the core by the game mode.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TLSInteractable.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UENUM()
enum class ETLSInteractKind : uint8
{
        EvidencePickup UMETA(DisplayName = "Evidence Pickup"),   // collect (and observe)
        ObserveEvidence UMETA(DisplayName = "Observe Evidence"), // look, do not touch
        Flavor UMETA(DisplayName = "Flavor"),                    // pure narration
        ExamineTable UMETA(DisplayName = "Examination Table"),   // open the table UI
        LedgerBoard UMETA(DisplayName = "Ledger Board"),         // open the deduction board UI
        SaveDesk UMETA(DisplayName = "Save Desk"),               // manual save (QUEST_ARCH 8)
        Bed UMETA(DisplayName = "Bed")                           // end the day
};

UCLASS()
class TLS_API ATLSInteractable : public AActor
{
        GENERATED_BODY()

public:
        ATLSInteractable();

        UPROPERTY(EditAnywhere, Category = "TLS")
        FString InteractId;

        UPROPERTY(EditAnywhere, Category = "TLS")
        FString DisplayName;

        UPROPERTY(EditAnywhere, Category = "TLS")
        FString Note;

        UPROPERTY(EditAnywhere, Category = "TLS")
        ETLSInteractKind Kind = ETLSInteractKind::Flavor;

        /** Core evidence id for pickup/observe kinds. */
        UPROPERTY(EditAnywhere, Category = "TLS")
        FString EvidenceId;

        /** First narrative day the object exists (mill scene = day 2). */
        UPROPERTY(EditAnywhere, Category = "TLS")
        int32 SpawnDay = 1;

        /** Marks the object as already used (evidence taken etc.). */
        UPROPERTY(VisibleAnywhere, Category = "TLS")
        bool bConsumed = false;

        void SetBlockoutColor(const FColor& Color);
        void SetInteractScale(float ScaleXY, float ScaleZ);
        void MarkConsumed();

protected:
        UPROPERTY(VisibleAnywhere, Category = "TLS")
        UStaticMeshComponent* BodyVisual;

        UPROPERTY(VisibleAnywhere, Category = "TLS")
        UTextRenderComponent* PromptLabel;
};
