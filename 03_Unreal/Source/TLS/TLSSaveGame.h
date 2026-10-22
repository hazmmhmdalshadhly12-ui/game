// THE LAST SIN: The Sin-Eater - M1
// TLSSaveGame: thin UE save-game carrier. The full game state lives inside
// the engine-agnostic core (tls::Game) as a compact JSON payload string;
// UE only stores/loads that string in a slot. Round-trip verified by the
// standalone core tests (byte-stable, tools/core_tests).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/SaveGame.h"
#include "TLSSaveGame.generated.h"

UCLASS()
class TLS_API UTLSSaveGame : public USaveGame
{
        GENERATED_BODY()

public:
        /** Compact JSON payload produced by tls::Game::SaveToString(). */
        UPROPERTY(VisibleAnywhere, Category = "TLS")
        FString Payload;

        /** Narrative day the save was written on (for the load UI). */
        UPROPERTY(VisibleAnywhere, Category = "TLS")
        int32 Day = 1;

        /** Wall-clock stamp (epoch seconds) for save-slot ordering. */
        UPROPERTY(VisibleAnywhere, Category = "TLS")
        int64 Timestamp = 0;
};
