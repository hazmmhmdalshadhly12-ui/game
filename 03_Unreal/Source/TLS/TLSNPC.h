// THE LAST SIN: The Sin-Eater - M1
// TLSNPC: blockout villager. A coloured capsule standing at its schedule
// post; the label shows the canon name. Talking routes into the core
// dialogue engine via the game mode. Visual fidelity arrives with the real
// character assets in later milestones - this is the M1 dialogue-ready
// blockout the milestone plan asks for.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TLSNPC.generated.h"

class UStaticMeshComponent;
class UTextRenderComponent;

UCLASS()
class TLS_API ATLSNPC : public AActor
{
        GENERATED_BODY()

public:
        ATLSNPC();

        /** Core NPC id (CHR-xx / T3-xx). */
        UPROPERTY(EditAnywhere, Category = "TLS")
        FString NpcId;

        /** Display name (canon name from the registries). */
        UPROPERTY(EditAnywhere, Category = "TLS")
        FString DisplayName;

        /** Dialogue id offered on interaction (empty = ambient only). */
        UPROPERTY(EditAnywhere, Category = "TLS")
        FString DialogueId;

        /** Daily-schedule bark shown when the player walks close. */
        UPROPERTY(EditAnywhere, Category = "TLS")
        FString Bark;

        void SetBlockoutColor(const FColor& Color);

        /** Public setter - the game mode may not touch the protected label. */
        void SetNameLabelText(const FString& Text);

protected:
        UPROPERTY(VisibleAnywhere, Category = "TLS")
        UStaticMeshComponent* BodyVisual;

        UPROPERTY(VisibleAnywhere, Category = "TLS")
        UTextRenderComponent* NameLabel;
};
