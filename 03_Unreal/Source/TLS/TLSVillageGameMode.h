// THE LAST SIN: The Sin-Eater - M1
// TLSVillageGameMode: the M1 vertical-slice game mode.
//  - owns the engine-agnostic core state (tls::Game) and feeds it the
//    05_Narrative JSON data (same files the standalone tests run on);
//  - builds the Blackthorne blockout procedurally from
//    05_Narrative/world/blackthorne_blockout.json (no .umap required);
//  - spawns dialogue-ready blockout NPCs and day-gated interactables;
//  - drives the code-built UI panels, the save slot and the placeholder
//    weather ambience (procedural audio).
// The calibration room (M0) keeps its own game mode pinned on
// L_TLS_TestRoom by the import automation.
// Note: the pure C++ core is held behind pointers to keep the UnrealHeader
// tool away from engine-independent headers (Core/ stays UHT-free).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "TLSVillageGameMode.generated.h"

namespace tls { class Game; class JsonValue; }

class ATLSNPC;
class ATLSInteractable;
class ADirectionalLight;
class AExponentialHeightFog;
class UTLSHUDWidget;
class UTLSDialogueWidget;
class UTLSLedgerWidget;
class UTLSJournalWidget;
class UTLSProceduralAudioComponent;

UCLASS()
class TLS_API ATLSVillageGameMode : public AGameModeBase
{
        GENERATED_BODY()

public:
        ATLSVillageGameMode();
        virtual ~ATLSVillageGameMode();

        virtual void StartPlay() override;
        virtual void Tick(float DeltaSeconds) override;
        virtual void EndPlay(const EEndPlayReason::Type Reason) override;

        // ---- input entry points (called by ATLSCharacter) ----
        void OnInteractPressed();
        void OnJournalToggle();
        void OnCancelPressed();
        void OnDigitPressed(int32 Digit);
        void OnRestorePressed();

        UFUNCTION(Exec)
        void TLSNewGame();

protected:
        /** Root of the narrative data (relative to the project dir). */
        UPROPERTY(Config)
        FString NarrativeRoot = TEXT("../05_Narrative");

private:
        // ---- data loading ----
        bool LoadCoreData();
        bool LoadWorldLayout();

        // ---- world construction ----
        void BuildVillage();
        void SpawnBuildings();
        void SpawnProps();
        void SpawnPaths();
        void SpawnNPCs();
        void SpawnInteractables(bool bRespawnForNewDay);
        void SetupLightingAndWeather();
        class AStaticMeshActor* SpawnBox(const FVector& Center, const FVector& Scale, const FColor& Color,
                const FString& Label, bool bCollision = true);
        class AStaticMeshActor* SpawnCylinder(const FVector& Center, const FVector& Scale, const FColor& Color,
                const FRotator& Rotation, const FString& Label);
        class AStaticMeshActor* SpawnCone(const FVector& Center, const FVector& Scale, const FColor& Color,
                const FString& Label);
        bool GetBlockoutMaterial(class UMaterialInterface*& OutMaterial);

        // ---- area tracking ----
        void TrackPlayerAreas();
        FVector GetPlayerLocation() const;

        // ---- interaction routing ----
        void TryInteract();
        void InteractWithNPC(ATLSNPC* NPC);
        void InteractWithObject(ATLSInteractable* Object);
        ATLSNPC* FindNearestNPC(float MaxDistance) const;
        ATLSInteractable* FindNearestInteractable(float MaxDistance) const;
        void OpenTableUI();
        void OpenBoardUI();

        // ---- UI ----
        void CreateWidgets();
        void RefreshHUD();
        void RefreshDialogueUI();
        void RefreshLedgerUI();
        void RefreshJournalUI();

        // ---- day / weather ----
        void ApplyDayPresentation();
        void AdvanceDay();

        // ---- save ----
        void SaveAtDesk();
        void TryContinueFromSlot();

        // ---- helpers ----
        // NOTE: static member functions cannot be const-qualified (C++ rule) -
        // an earlier draft declared this 'const' and would not compile.
        static FColor PaletteColor(const std::string& Key, const FColor& Default);
        static FString ToFString(const std::string& S);

        // ---- core state (engine-agnostic; see Core/TLSGameState.h) ----
        tls::Game* Core;

        // ---- spawned world ----
        UPROPERTY(Transient)
        TArray<ATLSNPC*> Villagers;

        UPROPERTY(Transient)
        TArray<ATLSInteractable*> Interactables;

        UPROPERTY(Transient)
        ADirectionalLight* SunLight;

        UPROPERTY(Transient)
        AExponentialHeightFog* HeightFog;

        UPROPERTY(Transient)
        UTLSProceduralAudioComponent* Audio;

        // ---- UI ----
        UPROPERTY(Transient)
        UTLSHUDWidget* HUDWidget;

        UPROPERTY(Transient)
        UTLSDialogueWidget* DialogueWidget;

        UPROPERTY(Transient)
        UTLSLedgerWidget* LedgerWidget;

        UPROPERTY(Transient)
        UTLSJournalWidget* JournalWidget;

        // ---- UI mode ----
        enum class EPanelMode : uint8 { None, Dialogue, Table, Board, Journal };
        EPanelMode PanelMode = EPanelMode::None;

        // ledger/table selection state
        TArray<FString> SelectableEvidenceIds;
        int32 FirstSelectedIndex = INDEX_NONE;

        // area rects (core area id -> rect in cm)
        struct FAreaRect { FString Id; float MinX; float MinY; float MaxX; float MaxY; };
        TArray<FAreaRect> AreaRects;
        TMap<FString, FVector> AreaCenters;

        // world bookkeeping
        tls::JsonValue* WorldLayout = nullptr;
        bool bWorldBuilt = false;
        bool bBellRung = false;
        float AreaTrackTimer = 0.0f;
        FString LastVerdictLine;
};
