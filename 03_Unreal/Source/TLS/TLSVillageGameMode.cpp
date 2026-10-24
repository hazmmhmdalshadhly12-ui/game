// THE LAST SIN: The Sin-Eater - M1
// TLSVillageGameMode.cpp

#include "TLSVillageGameMode.h"

#include "Components/AudioComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

#include "Core/TLSGameState.h"
#include "Core/TLSJson.h"
#include "Core/TLSCoreTypes.h"
#include "TLSCharacter.h"
#include "TLSInteractable.h"
#include "TLSNPC.h"
#include "TLSProceduralAudio.h"
#include "TLSSaveGame.h"
#include "TLSWidgets.h"

namespace
{
        // dialogue offered by each story NPC in the slice
        const TCHAR* DialogueForNpc(const FString& NpcId)
        {
                if (NpcId == TEXT("CHR-03")) { return TEXT("DLG-GWENDOLYN-C1"); }
                if (NpcId == TEXT("CHR-04")) { return TEXT("DLG-CRANE-C1"); }
                if (NpcId == TEXT("CHR-06")) { return TEXT("DLG-MAIR-C1"); }
                if (NpcId == TEXT("CHR-13")) { return TEXT("DLG-COLES-C1"); }
                if (NpcId == TEXT("CHR-17")) { return TEXT("DLG-IFOR-C2"); }
                return TEXT("");
        }

        FColor TierColor(int Tier)
        {
                switch (Tier)
                {
                case 1: return FColor::FromHex("E8A34D");   // candle - story
                case 2: return FColor::FromHex("D9CBB2");   // paper - secondary
                default: return FColor::FromHex("5A6B4A");  // moss - background
                }
        }

        ETLSInteractKind KindFromString(const FString& Kind)
        {
                if (Kind == TEXT("evidence_pickup")) { return ETLSInteractKind::EvidencePickup; }
                if (Kind == TEXT("observe_evidence")) { return ETLSInteractKind::ObserveEvidence; }
                if (Kind == TEXT("examine_table")) { return ETLSInteractKind::ExamineTable; }
                if (Kind == TEXT("ledger_board")) { return ETLSInteractKind::LedgerBoard; }
                if (Kind == TEXT("save_desk")) { return ETLSInteractKind::SaveDesk; }
                if (Kind == TEXT("bed")) { return ETLSInteractKind::Bed; }
                return ETLSInteractKind::Flavor;
        }

        FColor KindColor(ETLSInteractKind Kind)
        {
                switch (Kind)
                {
                case ETLSInteractKind::EvidencePickup: return FColor::FromHex("E8A34D");
                case ETLSInteractKind::ObserveEvidence: return FColor::FromHex("7FA8C9");
                case ETLSInteractKind::ExamineTable: return FColor::FromHex("6E5340");
                case ETLSInteractKind::LedgerBoard: return FColor::FromHex("D9CBB2");
                case ETLSInteractKind::SaveDesk: return FColor::FromHex("6E5340");
                case ETLSInteractKind::Bed: return FColor::FromHex("1C2226");
                default: return FColor::FromHex("5A6B4A");
                }
        }

}

ATLSVillageGameMode::ATLSVillageGameMode()
{
        PrimaryActorTick.bCanEverTick = true;
        PrimaryActorTick.TickInterval = 0.1f;
        DefaultPawnClass = ATLSCharacter::StaticClass();

        Core = new tls::Game();
        WorldLayout = new tls::JsonValue();

        Audio = CreateDefaultSubobject<UTLSProceduralAudioComponent>(TEXT("Ambience"));
}

ATLSVillageGameMode::~ATLSVillageGameMode()
{
        delete Core;
        delete WorldLayout;
}

void ATLSVillageGameMode::EndPlay(const EEndPlayReason::Type Reason)
{
        // The console command binds a UObject delegate - it MUST be unregistered
        // here or it dangles across PIE sessions (the console manager is global).
        IConsoleManager::Get().UnregisterConsoleObject(TEXT("TLS.NewGame"));
        if (Audio) { Audio->DestroyComponent(); }
        Super::EndPlay(Reason);
}

void ATLSVillageGameMode::StartPlay()
{
        Super::StartPlay();

        // guarantee a pawn on the empty generated map (M0 pattern)
        if (UWorld* World = GetWorld())
        {
                for (FConstControllerIterator It = World->GetControllerIterator(); It; ++It)
                {
                        if (APlayerController* PC = Cast<APlayerController>(*It))
                        {
                                if (!PC->GetPawn())
                                {
                                        RestartPlayerAtTransform(PC, FTransform(FRotator(0.0f, 90.0f, 0.0f), FVector(0.0f, -100.0f, 110.0f)));
                                }
                        }
                }
        }

        if (!LoadCoreData())
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] Core narrative data failed to load - the slice cannot run."));
                UE_LOG(LogTemp, Error, TEXT("[TLS] Expected data under: %s"), *(FPaths::ProjectDir() + NarrativeRoot));
                return;
        }

        if (LoadWorldLayout())
        {
                BuildVillage();
        }

        CreateWidgets();

        // console helper (dev): TLS.NewGame restarts the slice from Day 1
        IConsoleManager::Get().RegisterConsoleCommand(TEXT("TLS.NewGame"),
                TEXT("Restart the M1 slice from Day 1"),
                FConsoleCommandDelegate::CreateUObject(this, &ATLSVillageGameMode::TLSNewGame));

        TryContinueFromSlot();
        if (!Core->IsValid())
        {
                Core->NewGame();
        }

        ApplyDayPresentation();
        RefreshHUD();
        RefreshJournalUI();

        UE_LOG(LogTemp, Log, TEXT("[TLS] Blackthorne slice ready: Day %d, %s."),
                Core->CurrentDay(), UTF8_TO_TCHAR(tls::ToString(Core->GetTimeOfDay())));
}

// ------------------------------------------------------------------ data

bool ATLSVillageGameMode::LoadCoreData()
{
        const FString Root = FPaths::ProjectDir() + NarrativeRoot;

        auto LoadJson = [&Root](const FString& Relative, tls::JsonValue& Out) -> bool
        {
                const FString Path = Root / Relative;
                FString Content;
                if (!FFileHelper::LoadFileToString(Content, *Path))
                {
                        UE_LOG(LogTemp, Error, TEXT("[TLS] Missing data file: %s"), *Path);
                        return false;
                }
                const std::string StdContent(TCHAR_TO_UTF8(*Content));
                tls::JsonParseResult P = tls::JsonParse(StdContent);
                if (!P.Ok)
                {
                        UE_LOG(LogTemp, Error, TEXT("[TLS] JSON error in %s (line %d col %d): %s"),
                                *Path, P.Line, P.Column, UTF8_TO_TCHAR(P.Error.c_str()));
                        return false;
                }
                Out = P.Value;
                return true;
        };

        std::string Err;
        tls::JsonValue Evidence, Quests, Sim;

        if (!LoadJson(TEXT("evidence/evidence_slice.json"), Evidence)) { return false; }
        if (!Core->LoadEvidenceData(Evidence, Err))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] evidence_slice load failed: %s"), UTF8_TO_TCHAR(Err.c_str()));
                return false;
        }

        if (!LoadJson(TEXT("quests/quests_slice.json"), Quests)) { return false; }
        if (!Core->LoadQuestData(Quests, Err))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] quests_slice load failed: %s"), UTF8_TO_TCHAR(Err.c_str()));
                return false;
        }

        if (!LoadJson(TEXT("sim/sim_blackthorne.json"), Sim)) { return false; }
        if (!Core->LoadSimData(Sim, Err))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] sim_blackthorne load failed: %s"), UTF8_TO_TCHAR(Err.c_str()));
                return false;
        }

        const TCHAR* Dialogues[] = {
                TEXT("dialogues/dlg_chr003_gwendolyn_c1.json"),
                TEXT("dialogues/dlg_chr004_crane_c1.json"),
                TEXT("dialogues/dlg_chr013_coles_c1.json"),
                TEXT("dialogues/dlg_chr006_mair_c1.json"),
                TEXT("dialogues/dlg_chr017_ifor_c2.json"),
        };
        // M3.8: the case layer must be loaded BEFORE the dialogues so the
        // dialogue -> case-fact bridge can be validated against the testimony
        // registry at load time (bad reveal_facts refuse the session).
        tls::JsonValue CaseFacts;
        if (!LoadJson(TEXT("case_facts/case_facts_slice.json"), CaseFacts)) { return false; }
        if (!Core->LoadCaseFactsData(CaseFacts, Err))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] case_facts_slice load failed: %s"), UTF8_TO_TCHAR(Err.c_str()));
                return false;
        }

        tls::JsonValue Deduction;
        if (!LoadJson(TEXT("deduction/deduction_slice.json"), Deduction)) { return false; }
        if (!Core->LoadDeductionData(Deduction, Err))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] deduction_slice load failed: %s"), UTF8_TO_TCHAR(Err.c_str()));
                return false;
        }

        for (const TCHAR* Relative : Dialogues)
        {
                tls::JsonValue Dlg;
                if (!LoadJson(Relative, Dlg)) { return false; }
                if (!Core->LoadDialogueData(Dlg, Err))
                {
                        UE_LOG(LogTemp, Error, TEXT("[TLS] dialogue load failed (%s): %s"), Relative, UTF8_TO_TCHAR(Err.c_str()));
                        return false;
                }
        }

        // M3.8: refuse a session whose dialogue reveal_facts do not resolve
        // against the case-fact ledger (unknown fact, or a speaker who owns
        // no testimony for it).
        if (!Core->ValidateDialogueCaseLinks(Err))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] dialogue/case-fact bridge invalid: %s"), UTF8_TO_TCHAR(Err.c_str()));
                return false;
        }

        // M2.1 rumor defs - the UE slice shares the same village gossip the
        // core tests run on (witness events, player hearings, leaks).
        tls::JsonValue Rumors;
        if (!LoadJson(TEXT("rumors/rumors_blackthorne.json"), Rumors)) { return false; }
        if (!Core->LoadRumorData(Rumors, Err))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] rumors_blackthorne load failed: %s"), UTF8_TO_TCHAR(Err.c_str()));
                return false;
        }
        return true;
}

bool ATLSVillageGameMode::LoadWorldLayout()
{
        const FString Path = FPaths::ProjectDir() + NarrativeRoot / TEXT("world/blackthorne_blockout.json");
        FString Content;
        if (!FFileHelper::LoadFileToString(Content, *Path))
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] Missing world layout: %s"), *Path);
                return false;
        }
        tls::JsonParseResult P = tls::JsonParse(std::string(TCHAR_TO_UTF8(*Content)));
        if (!P.Ok)
        {
                UE_LOG(LogTemp, Error, TEXT("[TLS] World layout JSON error (line %d): %s"), P.Line, UTF8_TO_TCHAR(P.Error.c_str()));
                return false;
        }
        *WorldLayout = P.Value;
        return true;
}

// ------------------------------------------------------------------ world

bool ATLSVillageGameMode::GetBlockoutMaterial(UMaterialInterface*& OutMaterial)
{
        OutMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/TLS/Materials/M_TLS_Blockout.M_TLS_Blockout"));
        if (!OutMaterial)
        {
                UE_LOG(LogTemp, Warning, TEXT("[TLS] M_TLS_Blockout missing (run 02_import_and_calibrate.bat) - blockout renders grey."));
        }
        return OutMaterial != nullptr;
}

FString ATLSVillageGameMode::ToFString(const std::string& S)
{
        return FString(UTF8_TO_TCHAR(S.c_str()));
}

FColor ATLSVillageGameMode::PaletteColor(const std::string& Key, const FColor& Default)
{
        if (!WorldLayout) { return Default; }
        const tls::JsonValue* Palette = WorldLayout->Find("palette");
        if (!Palette) { return Default; }
        const tls::JsonValue* Hex = Palette->Find(Key);
        if (!Hex || !Hex->IsString()) { return Default; }
        return FColor::FromHex(ToFString(Hex->AsString()));
}

AStaticMeshActor* ATLSVillageGameMode::SpawnBox(const FVector& Center, const FVector& Scale, const FColor& Color,
        const FString& Label, bool bCollision)
{
        UWorld* World = GetWorld();
        if (!World) { return nullptr; }

        UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
        if (!Cube) { return nullptr; }

        const FTransform T(FQuat::Identity, Center);
        AStaticMeshActor* Actor = World->SpawnActorDeferred<AStaticMeshActor>(
                AStaticMeshActor::StaticClass(), T, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Actor) { return nullptr; }

        UStaticMeshComponent* Comp = Actor->GetStaticMeshComponent();
        Comp->SetStaticMesh(Cube);
        Comp->SetMobility(EComponentMobility::Movable);
        Comp->SetRelativeScale3D(Scale);
        if (!bCollision)
        {
                Comp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        }

        UMaterialInterface* BaseMaterial = nullptr;
        if (GetBlockoutMaterial(BaseMaterial))
        {
                UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(BaseMaterial, Comp);
                if (MID)
                {
                        MID->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(Color));
                        Comp->SetMaterial(0, MID);
                }
        }

        Actor->FinishSpawning(T);
        Actor->SetActorLabel(Label);
        return Actor;
}

AStaticMeshActor* ATLSVillageGameMode::SpawnCylinder(const FVector& Center, const FVector& Scale, const FColor& Color,
        const FRotator& Rotation, const FString& Label)
{
        UWorld* World = GetWorld();
        if (!World) { return nullptr; }

        UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
        if (!Cylinder) { return nullptr; }

        const FTransform T(Rotation, Center);
        AStaticMeshActor* Actor = World->SpawnActorDeferred<AStaticMeshActor>(
                AStaticMeshActor::StaticClass(), T, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Actor) { return nullptr; }

        UStaticMeshComponent* Comp = Actor->GetStaticMeshComponent();
        Comp->SetStaticMesh(Cylinder);
        Comp->SetMobility(EComponentMobility::Movable);
        Comp->SetRelativeScale3D(Scale);

        UMaterialInterface* BaseMaterial = nullptr;
        if (GetBlockoutMaterial(BaseMaterial))
        {
                UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(BaseMaterial, Comp);
                if (MID)
                {
                        MID->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(Color));
                        Comp->SetMaterial(0, MID);
                }
        }

        Actor->FinishSpawning(T);
        Actor->SetActorLabel(Label);
        return Actor;
}

AStaticMeshActor* ATLSVillageGameMode::SpawnCone(const FVector& Center, const FVector& Scale, const FColor& Color,
        const FString& Label)
{
        UWorld* World = GetWorld();
        if (!World) { return nullptr; }
        UStaticMesh* Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"));
        if (!Cone) { return nullptr; }

        const FTransform T(FQuat::Identity, Center);
        AStaticMeshActor* Actor = World->SpawnActorDeferred<AStaticMeshActor>(
                AStaticMeshActor::StaticClass(), T, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Actor) { return nullptr; }
        UStaticMeshComponent* Comp = Actor->GetStaticMeshComponent();
        Comp->SetStaticMesh(Cone);
        Comp->SetMobility(EComponentMobility::Movable);
        Comp->SetRelativeScale3D(Scale);
        UMaterialInterface* BaseMaterial = nullptr;
        if (GetBlockoutMaterial(BaseMaterial))
        {
                UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(BaseMaterial, Comp);
                if (MID)
                {
                        MID->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(Color));
                        Comp->SetMaterial(0, MID);
                }
        }
        Actor->FinishSpawning(T);
        Actor->SetActorLabel(Label);
        return Actor;
}

void ATLSVillageGameMode::BuildVillage()
{
        UWorld* UWorldPtr = GetWorld();
        if (!UWorldPtr || !WorldLayout || bWorldBuilt) { return; }
        const tls::JsonValue& World = *WorldLayout;
        bWorldBuilt = true;

        // areas (for tracking + NPC placement)
        if (const tls::JsonValue* Areas = World.Find("areas"))
        {
                for (size_t I = 0; I < Areas->Size(); ++I)
                {
                        const tls::JsonValue* A = Areas->At(I);
                        if (!A) { continue; }
                        FAreaRect R;
                        R.Id = ToFString(A->GetString("id", ""));
                        const tls::JsonValue* Rect = A->Find("rect_m");
                        if (!Rect || Rect->Size() < 4) { continue; }
                        const float X = static_cast<float>(Rect->At(0)->AsNumber());
                        const float Y = static_cast<float>(Rect->At(1)->AsNumber());
                        const float W = static_cast<float>(Rect->At(2)->AsNumber());
                        const float H = static_cast<float>(Rect->At(3)->AsNumber());
                        R.MinX = (X - W * 0.5f) * 100.0f;
                        R.MaxX = (X + W * 0.5f) * 100.0f;
                        R.MinY = (Y - H * 0.5f) * 100.0f;
                        R.MaxY = (Y + H * 0.5f) * 100.0f;
                        AreaRects.Add(R);
                        AreaCenters.Add(R.Id, FVector(X * 100.0f, Y * 100.0f, 0.0f));
                }
        }

        // ground 140 x 160 m, top surface at Z = 0
        SpawnBox(FVector(0.0f, 0.0f, -5.0f), FVector(140.0f, 160.0f, 0.1f),
                PaletteColor("MSS", FColor::FromHex("5A6B4A")), TEXT("TLS_Ground"));

        // river band (south)
        if (const tls::JsonValue* Water = World.Find("water"))
        {
                const tls::JsonValue* Band = Water->Find("band_m");
                if (Band && Band->Size() >= 4)
                {
                        const float X = static_cast<float>(Band->At(0)->AsNumber()) * 100.0f;
                        const float Y = static_cast<float>(Band->At(1)->AsNumber()) * 100.0f;
                        const float W = static_cast<float>(Band->At(2)->AsNumber());
                        const float H = static_cast<float>(Band->At(3)->AsNumber());
                        SpawnBox(FVector(X + W * 50.0f, Y + H * 50.0f, -12.0f), FVector(W, H, 0.12f),
                                PaletteColor("SBL", FColor::FromHex("7FA8C9")), TEXT("TLS_AfonDdu"));
                }
        }

        SpawnBuildings();
        SpawnProps();
        SpawnPaths();
        SpawnNPCs();
        SpawnInteractables(false);
        SetupLightingAndWeather();

        UE_LOG(LogTemp, Log, TEXT("[TLS] Blackthorne blockout built: %d areas, %d interactables, %d villagers."),
                AreaRects.Num(), Interactables.Num(), Villagers.Num());
}

void ATLSVillageGameMode::SpawnBuildings()
{
        if (!WorldLayout) { return; }
        const tls::JsonValue& World = *WorldLayout;
        const tls::JsonValue* Buildings = World.Find("buildings");
        if (!Buildings) { return; }

        const FColor StoneColor = PaletteColor("SLT", FColor::FromHex("3A4550"));
        const FColor InkColor = PaletteColor("INK", FColor::FromHex("1C2226"));
        const FColor WoodColor = PaletteColor("BRF", FColor::FromHex("6E5340"));

        for (size_t I = 0; I < Buildings->Size(); ++I)
        {
                const tls::JsonValue* B = Buildings->At(I);
                if (!B) { continue; }

                const tls::JsonValue* Rect = B->Find("rect_m");
                if (!Rect || Rect->Size() < 4) { continue; }
                const float X = static_cast<float>(Rect->At(0)->AsNumber());
                const float Y = static_cast<float>(Rect->At(1)->AsNumber());
                const float W = static_cast<float>(Rect->At(2)->AsNumber());
                const float H = static_cast<float>(Rect->At(3)->AsNumber());
                const float Height = static_cast<float>(B->GetNumber("height_m", 4.0));
                const FString Label = ToFString(B->GetString("id", ""));

                const tls::JsonValue* Pal = B->Find("palette");
                const FColor WallColor = Pal ? PaletteColor(Pal->GetString("walls", "SLT"), StoneColor) : StoneColor;
                const FColor RoofColor = Pal ? PaletteColor(Pal->GetString("roof", "SLT"), StoneColor) : StoneColor;
                const FColor LightColor = Pal && Pal->Find("window_light")
                        ? PaletteColor(Pal->GetString("window_light", "CDL"), FColor::FromHex("E8A34D"))
                        : FColor::FromHex("E8A34D");

                // walls (top at Height)
                SpawnBox(FVector(X * 100.0f, Y * 100.0f, Height * 50.0f), FVector(W, H, Height), WallColor, Label);

                // flat blockout roof lid
                SpawnBox(FVector(X * 100.0f, Y * 100.0f, Height * 100.0f + 15.0f), FVector(W + 0.8f, H + 0.8f, 0.3f),
                        RoofColor, Label + TEXT("_Roof"), false);

                // features
                const std::vector<std::string> Features = B->GetStringList("features");
                for (const std::string& F : Features)
                {
                        if (F == "square_tower")
                        {
                                const float TX = (X + W * 0.5f - 1.75f) * 100.0f;
                                SpawnBox(FVector(TX, Y * 100.0f, 600.0f), FVector(3.5f, 3.5f, 12.0f), WallColor, Label + TEXT("_Tower"));
                                SpawnCone(FVector(TX, Y * 100.0f, 1280.0f), FVector(4.0f, 4.0f, 2.6f), RoofColor, Label + TEXT("_TowerSpire"));
                        }
                        else if (F == "water_wheel_south")
                        {
                                SpawnCylinder(FVector(X * 100.0f, (Y - H * 0.5f - 1.0f) * 100.0f, -60.0f),
                                        FVector(4.2f, 4.2f, 0.5f), WoodColor,
                                        FRotator(90.0f, 0.0f, 0.0f), Label + TEXT("_Wheel"));
                        }
                        else if (F == "hearth_chimney" || F == "oven_chimney")
                        {
                                SpawnBox(FVector((X + W * 0.25f) * 100.0f, Y * 100.0f, Height * 100.0f + 60.0f),
                                        FVector(0.6f, 0.6f, 1.0f), InkColor, Label + TEXT("_Chimney"), false);
                        }
                }

                // candle-lit windows for inhabited buildings
                if (Pal && Pal->Find("window_light"))
                {
                        const int32 Floors = FMath::Max(1, FMath::RoundToInt(Height / 3.5f));
                        for (int32 Fl = 0; Fl < Floors; ++Fl)
                        {
                                for (int32 Wi = 0; Wi < 2; ++Wi)
                                {
                                        const float WX = (X - W * 0.25f + Wi * W * 0.5f) * 100.0f;
                                        const float WY = (Y - H * 0.5f - 0.06f) * 100.0f;
                                        const float WZ = 150.0f + Fl * 350.0f;
                                        SpawnBox(FVector(WX, WY, WZ), FVector(0.7f, 0.12f, 0.9f), LightColor,
                                                Label + TEXT("_Window"), false);
                                }
                        }
                }
        }

        // locked doors with documented reasons (WORLD_REGISTRY 4: no silent decor doors)
        if (const tls::JsonValue* Doors = World.Find("doors"))
        {
                for (size_t I = 0; I < Doors->Size(); ++I)
                {
                        const tls::JsonValue* D = Doors->At(I);
                        if (!D) { continue; }
                        const std::string BuildingId = D->GetString("building", "");
                        FVector DoorPos(0.0f, 0.0f, 110.0f);
                        for (size_t K = 0; K < Buildings->Size(); ++K)
                        {
                                const tls::JsonValue* B = Buildings->At(K);
                                if (B && B->GetString("id", "") == BuildingId)
                                {
                                        const tls::JsonValue* Rect = B->Find("rect_m");
                                        if (Rect && Rect->Size() >= 4)
                                        {
                                                const float BX = static_cast<float>(Rect->At(0)->AsNumber());
                                                const float BY = static_cast<float>(Rect->At(1)->AsNumber());
                                                const float BH = static_cast<float>(Rect->At(3)->AsNumber());
                                                DoorPos = FVector(BX * 100.0f, (BY - BH * 0.5f) * 100.0f - 80.0f, 110.0f);
                                        }
                                        break;
                                }
                        }
                        UWorld* W = GetWorld();
                        if (!W) { continue; }
                        ATLSInteractable* DoorActor = W->SpawnActor<ATLSInteractable>(ATLSInteractable::StaticClass(),
                                FTransform(DoorPos));
                        if (DoorActor)
                        {
                                DoorActor->InteractId = ToFString(D->GetString("id", ""));
                                DoorActor->DisplayName = TEXT("Door");
                                DoorActor->Note = ToFString(D->GetString("reason", ""));
                                DoorActor->Kind = ETLSInteractKind::Flavor;
                                DoorActor->SpawnDay = 1;
                                DoorActor->SetBlockoutColor(InkColor);
                                DoorActor->SetInteractScale(1.4f, 2.2f);
                                Interactables.Add(DoorActor);
                        }
                }
        }
}

void ATLSVillageGameMode::SpawnProps()
{
        if (!WorldLayout) { return; }
        const tls::JsonValue& World = *WorldLayout;
        const tls::JsonValue* Props = World.Find("props");
        if (!Props) { return; }

        const FColor StoneColor = PaletteColor("SLT", FColor::FromHex("3A4550"));
        const FColor WoodColor = PaletteColor("BRF", FColor::FromHex("6E5340"));
        const FColor WaterColor = PaletteColor("SBL", FColor::FromHex("7FA8C9"));
        const FColor HedgeColor(0x39, 0x46, 0x38, 0xFF);

        for (size_t I = 0; I < Props->Size(); ++I)
        {
                const tls::JsonValue* P = Props->At(I);
                if (!P) { continue; }
                const tls::JsonValue* Pos = P->Find("pos_m");
                if (!Pos || Pos->Size() < 2) { continue; }
                const float X = static_cast<float>(Pos->At(0)->AsNumber()) * 100.0f;
                const float Y = static_cast<float>(Pos->At(1)->AsNumber()) * 100.0f;
                const std::string Kind = P->GetString("kind", "");
                const FString Label = ToFString(P->GetString("id", ""));

                if (Kind == "tree")
                {
                        SpawnCylinder(FVector(X, Y, 125.0f), FVector(0.5f, 0.5f, 2.5f), WoodColor, Label + TEXT("_Trunk"));
                        SpawnBox(FVector(X, Y, 480.0f), FVector(7.0f, 7.0f, 4.6f), HedgeColor, Label + TEXT("_Canopy"), false);
                }
                else if (Kind == "well")
                {
                        SpawnCylinder(FVector(X, Y, 45.0f), FVector(1.6f, 1.6f, 0.9f), StoneColor, Label);
                }
                else if (Kind == "stone")
                {
                        SpawnBox(FVector(X, Y, 130.0f), FVector(0.5f, 0.9f, 2.6f), StoneColor, Label);
                }
                else if (Kind == "grave" || Kind == "gravestone")
                {
                        const float GH = Kind == "grave" ? 1.1f : 1.6f;
                        SpawnBox(FVector(X, Y, GH * 50.0f), FVector(0.7f, 0.2f, GH), StoneColor, Label);
                }
                else if (Kind == "graves_row")
                {
                        for (int32 G = 0; G < 7; ++G)
                        {
                                SpawnBox(FVector(X + G * 130.0f, Y + ((G % 2) == 0 ? 0.0f : 160.0f), 60.0f),
                                        FVector(0.6f, 0.2f, 1.2f), StoneColor, Label + FString::Printf(TEXT("_%d"), G));
                        }
                }
                else if (Kind == "bridge")
                {
                        SpawnBox(FVector(X, -680.0f, 20.0f), FVector(7.0f, 16.0f, 0.5f), WoodColor, Label);
                }
                else if (Kind == "race")
                {
                        SpawnBox(FVector(X, Y, -8.0f), FVector(4.0f, 3.0f, 0.12f), WaterColor, Label, false);
                }
                else if (Kind == "hedge_row")
                {
                        SpawnBox(FVector(X, Y, 65.0f), FVector(12.0f, 1.1f, 1.3f), HedgeColor, Label);
                }
                else if (Kind == "posts")
                {
                        for (int32 K = 0; K < 3; ++K)
                        {
                                SpawnBox(FVector(X + K * 150.0f, Y, 110.0f), FVector(0.18f, 0.18f, 2.2f), WoodColor, Label + TEXT("_Post"));
                        }
                }
        }
}

void ATLSVillageGameMode::SpawnPaths()
{
        if (!WorldLayout) { return; }
        const tls::JsonValue& World = *WorldLayout;
        const tls::JsonValue* Paths = World.Find("paths");
        if (!Paths) { return; }
        const FColor PathColor(0x4A, 0x43, 0x35, 0xFF);

        UWorld* W = GetWorld();
        if (!W) { return; }
        UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
        if (!Cube) { return; }

        for (size_t I = 0; I < Paths->Size(); ++I)
        {
                const tls::JsonValue* P = Paths->At(I);
                if (!P) { continue; }
                const tls::JsonValue* Points = P->Find("points_m");
                if (!Points || Points->Size() < 2) { continue; }
                const float Width = static_cast<float>(P->GetNumber("width_m", 3.0));

                for (size_t K = 0; K + 1 < Points->Size(); ++K)
                {
                        const tls::JsonValue* A = Points->At(K);
                        const tls::JsonValue* Bv = Points->At(K + 1);
                        if (!A || !Bv || A->Size() < 2 || Bv->Size() < 2) { continue; }
                        const float AX = static_cast<float>(A->At(0)->AsNumber()) * 100.0f;
                        const float AY = static_cast<float>(A->At(1)->AsNumber()) * 100.0f;
                        const float BX = static_cast<float>(Bv->At(0)->AsNumber()) * 100.0f;
                        const float BY = static_cast<float>(Bv->At(1)->AsNumber()) * 100.0f;
                        const FVector Center((AX + BX) * 0.5f, (AY + BY) * 0.5f, 1.0f);
                        const float LengthCm = FMath::Sqrt(FMath::Square(BX - AX) + FMath::Square(BY - AY));
                        const float Length = LengthCm / 100.0f + Width;
                        const float Angle = FMath::Atan2(BY - AY, BX - AX) * (180.0f / PI);
                        const FTransform T(FRotator(0.0f, Angle, 0.0f), Center);
                        AStaticMeshActor* Strip = W->SpawnActorDeferred<AStaticMeshActor>(
                                AStaticMeshActor::StaticClass(), T, nullptr, nullptr,
                                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
                        if (Strip)
                        {
                                UStaticMeshComponent* Comp = Strip->GetStaticMeshComponent();
                                Comp->SetStaticMesh(Cube);
                                Comp->SetMobility(EComponentMobility::Movable);
                                Comp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
                                Comp->SetRelativeScale3D(FVector(Length, Width, 0.02f));
                                UMaterialInterface* BaseMaterial = nullptr;
                                if (GetBlockoutMaterial(BaseMaterial))
                                {
                                        UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(BaseMaterial, Comp);
                                        if (MID)
                                        {
                                                MID->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(PathColor));
                                                Comp->SetMaterial(0, MID);
                                        }
                                }
                                Strip->FinishSpawning(T);
                        }
                }
        }
}

void ATLSVillageGameMode::SpawnNPCs()
{
        if (!WorldLayout) { return; }
        const tls::JsonValue* Posts = WorldLayout->Find("npc_posts");
        if (!Posts) { return; }
        UWorld* W = GetWorld();
        if (!W) { return; }

        for (size_t I = 0; I < Posts->Size(); ++I)
        {
                const tls::JsonValue* Post = Posts->At(I);
                if (!Post) { continue; }
                const std::string NpcId = Post->GetString("npc", "");
                const tls::JsonValue* Pos = Post->Find("pos_m");
                if (NpcId.empty() || !Pos || Pos->Size() < 2) { continue; }

                const tls::NPCDef* Npc = Core->Village().FindNpc(NpcId);
                ATLSNPC* Actor = W->SpawnActor<ATLSNPC>(ATLSNPC::StaticClass(), FTransform(
                        FRotator(0.0f, 180.0f, 0.0f),
                        FVector(static_cast<float>(Pos->At(0)->AsNumber()) * 100.0f,
                                static_cast<float>(Pos->At(1)->AsNumber()) * 100.0f, 0.0f)));
                if (!Actor) { continue; }

                Actor->NpcId = ToFString(NpcId);
                Actor->DisplayName = Npc ? ToFString(Npc->Name) : ToFString(NpcId);
                Actor->DialogueId = DialogueForNpc(Actor->NpcId);
                Actor->SetBlockoutColor(TierColor(Npc ? Npc->Tier : 3));
                Actor->SetNameLabelText(Actor->DisplayName);
                Villagers.Add(Actor);
        }
}

void ATLSVillageGameMode::SpawnInteractables(bool bRespawnForNewDay)
{
        if (!WorldLayout) { return; }
        const tls::JsonValue* List = WorldLayout->Find("interactables");
        if (!List) { return; }
        UWorld* W = GetWorld();
        if (!W) { return; }

        const int32 CurrentDay = Core->CurrentDay();

        for (size_t I = 0; I < List->Size(); ++I)
        {
                const tls::JsonValue* It = List->At(I);
                if (!It) { continue; }
                const std::string Id = It->GetString("id", "");
                const int32 Day = It->GetInt("day", 1);
                if (Day != CurrentDay) { continue; }

                bool bExists = false;
                for (ATLSInteractable* Existing : Interactables)
                {
                        if (Existing && Existing->InteractId == ToFString(Id)) { bExists = true; break; }
                }
                if (bExists) { continue; }

                const tls::JsonValue* Pos = It->Find("pos_m");
                if (!Pos || Pos->Size() < 2) { continue; }
                const ETLSInteractKind Kind = KindFromString(ToFString(It->GetString("kind", "flavor")));

                ATLSInteractable* Actor = W->SpawnActor<ATLSInteractable>(ATLSInteractable::StaticClass(), FTransform(
                        FVector(static_cast<float>(Pos->At(0)->AsNumber()) * 100.0f,
                                static_cast<float>(Pos->At(1)->AsNumber()) * 100.0f, 0.0f)));
                if (!Actor) { continue; }

                Actor->InteractId = ToFString(Id);
                Actor->Kind = Kind;
                Actor->EvidenceId = ToFString(It->GetString("evidence", ""));
                Actor->SpawnDay = Day;
                Actor->Note = ToFString(It->GetString("note", ""));
                Actor->DisplayName = Actor->Note.Left(60);
                Actor->SetBlockoutColor(KindColor(Kind));
                Actor->SetInteractScale(0.5f, 0.5f);
                Actor->SetPromptLabelText(ToFString(Id));
                Interactables.Add(Actor);
        }
}

void ATLSVillageGameMode::SetupLightingAndWeather()
{
        UWorld* World = GetWorld();
        if (!World) { return; }

        const FTransform SunTransform(FRotator(-45.0f, 40.0f, 0.0f), FVector(0.0f, 0.0f, 800.0f));
        SunLight = World->SpawnActorDeferred<ADirectionalLight>(
                ADirectionalLight::StaticClass(), SunTransform, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (SunLight)
        {
                if (ULightComponent* LightComp = SunLight->GetLightComponent())
                {
                        LightComp->SetMobility(EComponentMobility::Movable);
                        LightComp->Intensity = 2.2f;
                }
                SunLight->FinishSpawning(SunTransform);
        }

        const FTransform FogTransform(FVector(0.0f, 0.0f, 0.0f));
        HeightFog = World->SpawnActorDeferred<AExponentialHeightFog>(
                AExponentialHeightFog::StaticClass(), FogTransform, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (HeightFog)
        {
                HeightFog->FinishSpawning(FogTransform);
        }
}

// ------------------------------------------------------------------ tick / areas

void ATLSVillageGameMode::Tick(float DeltaSeconds)
{
        Super::Tick(DeltaSeconds);
        if (!bWorldBuilt) { return; }

        AreaTrackTimer += DeltaSeconds;
        if (AreaTrackTimer >= 0.25f)
        {
                AreaTrackTimer = 0.0f;
                TrackPlayerAreas();
                RefreshHUD();
        }
}

FVector ATLSVillageGameMode::GetPlayerLocation() const
{
        const UWorld* World = GetWorld();
        if (!World) { return FVector::ZeroVector; }
        for (FConstControllerIterator It = World->GetControllerIterator(); It; ++It)
        {
                if (const APlayerController* PC = Cast<APlayerController>(*It))
                {
                        if (const APawn* Pawn = PC->GetPawn()) { return Pawn->GetActorLocation(); }
                }
        }
        return FVector::ZeroVector;
}

void ATLSVillageGameMode::TrackPlayerAreas()
{
        const FVector Loc = GetPlayerLocation();
        for (const FAreaRect& R : AreaRects)
        {
                if (Loc.X >= R.MinX && Loc.X <= R.MaxX && Loc.Y >= R.MinY && Loc.Y <= R.MaxY)
                {
                        if (!Core->HasReachedArea(R.Id))
                        {
                                Core->NotifyReachArea(TCHAR_TO_UTF8(*R.Id));
                                if (R.Id == TEXT("AREA-CHURCHYARD") && !bBellRung && Core->CurrentDay() == 1)
                                {
                                        bBellRung = true;
                                        if (Audio) { Audio->PlayBell(); }
                                        if (HUDWidget) { HUDWidget->SetToast(TEXT("St. Cynog's bell answers the burial.")); }
                                }
                        }
                }
        }
}

// ------------------------------------------------------------------ interaction

ATLSNPC* ATLSVillageGameMode::FindNearestNPC(float MaxDistance) const
{
        ATLSNPC* Best = nullptr;
        float BestDist = MaxDistance;
        const FVector Loc = GetPlayerLocation();
        for (ATLSNPC* Npc : Villagers)
        {
                if (!Npc) { continue; }
                const float Dist = FVector::Dist(Loc, Npc->GetActorLocation());
                if (Dist < BestDist) { BestDist = Dist; Best = Npc; }
        }
        return Best;
}

ATLSInteractable* ATLSVillageGameMode::FindNearestInteractable(float MaxDistance) const
{
        ATLSInteractable* Best = nullptr;
        float BestDist = MaxDistance;
        const FVector Loc = GetPlayerLocation();
        for (ATLSInteractable* Obj : Interactables)
        {
                if (!Obj || Obj->bConsumed) { continue; }
                if (Obj->SpawnDay > Core->CurrentDay()) { continue; }
                const float Dist = FVector::Dist(Loc, Obj->GetActorLocation());
                if (Dist < BestDist) { BestDist = Dist; Best = Obj; }
        }
        return Best;
}

void ATLSVillageGameMode::OnInteractPressed()
{
        if (PanelMode == EPanelMode::Dialogue) { return; }
        // M3.8: on the deduction board, E is the deliberate act - speak the
        // selected accusation (with its confirm step). The world interaction
        // path stays exactly as it was.
        if (PanelMode == EPanelMode::Deduction)
        {
                ConfirmAccusation();
                return;
        }
        if (PanelMode != EPanelMode::None) { return; }
        TryInteract();
}

void ATLSVillageGameMode::TryInteract()
{
        if (ATLSInteractable* Obj = FindNearestInteractable(280.0f))
        {
                InteractWithObject(Obj);
                return;
        }
        if (ATLSNPC* Npc = FindNearestNPC(280.0f))
        {
                InteractWithNPC(Npc);
        }
}

void ATLSVillageGameMode::InteractWithNPC(ATLSNPC* NPC)
{
        if (!NPC) { return; }

        if (NPC->DialogueId.IsEmpty())
        {
                // background villager: today's bark from the schedule
                if (HUDWidget)
                {
                        const tls::NPCDef* Npc = Core->Village().FindNpc(std::string(TCHAR_TO_UTF8(*NPC->NpcId)));
                        if (Npc)
                        {
                                const std::vector<tls::ScheduleSegment>& Segments =
                                        (Core->Village().Tension() >= 3.0 && !Npc->ScheduleTension.empty())
                                        ? Npc->ScheduleTension : Npc->Schedule;
                                for (const tls::ScheduleSegment& S : Segments)
                                {
                                        if (!S.Bark.empty() && Core->Village().Hour() >= S.FromHour && Core->Village().Hour() < S.ToHour)
                                        {
                                                HUDWidget->SetToast(ToFString(Npc->Name) + TEXT(": \"") + ToFString(S.Bark) + TEXT("\""));
                                                return;
                                        }
                                }
                                HUDWidget->SetToast(ToFString(Npc->Name) + TEXT(" goes about their day."));
                        }
                }
                return;
        }

        std::string Err;
        if (Core->BeginDialogue(std::string(TCHAR_TO_UTF8(*NPC->DialogueId)), Err))
        {
                PanelMode = EPanelMode::Dialogue;
                if (DialogueWidget) { DialogueWidget->SetVisibility(ESlateVisibility::Visible); }
                RefreshDialogueUI();
        }
        else if (HUDWidget)
        {
                HUDWidget->SetToast(UTF8_TO_TCHAR(Err.c_str()));
        }
}

void ATLSVillageGameMode::InteractWithObject(ATLSInteractable* Object)
{
        if (!Object) { return; }

        switch (Object->Kind)
        {
        case ETLSInteractKind::EvidencePickup:
        {
                const std::string Ev = std::string(TCHAR_TO_UTF8(*Object->EvidenceId));
                Core->NotifyObserveEvidence(Ev);
                Core->NotifyCollectEvidence(Ev, "taken by Edmund");
                Object->MarkConsumed();
                const tls::EvidenceDef* Def = Core->Evidence().FindDef(Ev);
                if (HUDWidget && Def)
                {
                        HUDWidget->SetToast(FString::Printf(TEXT("Evidence taken: %s"), UTF8_TO_TCHAR(Def->Name.c_str())));
                }
                break;
        }
        case ETLSInteractKind::ObserveEvidence:
        {
                const std::string Ev = std::string(TCHAR_TO_UTF8(*Object->EvidenceId));
                std::string Note;
                Core->NotifyObserveEvidence(Ev, &Note);
                if (HUDWidget) { HUDWidget->SetToast(UTF8_TO_TCHAR(Note.c_str())); }
                break;
        }
        case ETLSInteractKind::Flavor:
                if (HUDWidget) { HUDWidget->SetToast(Object->Note); }
                break;
        case ETLSInteractKind::ExamineTable:
                OpenTableUI();
                break;
        case ETLSInteractKind::LedgerBoard:
                OpenBoardUI();
                break;
        case ETLSInteractKind::SaveDesk:
                SaveAtDesk();
                break;
        case ETLSInteractKind::Bed:
                AdvanceDay();
                break;
        }
}

void ATLSVillageGameMode::OpenTableUI()
{
        PanelMode = EPanelMode::Table;
        FirstSelectedIndex = INDEX_NONE;
        if (LedgerWidget) { LedgerWidget->SetVisibility(ESlateVisibility::Visible); }
        RefreshLedgerUI();
}

void ATLSVillageGameMode::OpenBoardUI()
{
        PanelMode = EPanelMode::Board;
        FirstSelectedIndex = INDEX_NONE;
        if (LedgerWidget) { LedgerWidget->SetVisibility(ESlateVisibility::Visible); }
        RefreshLedgerUI();
}

void ATLSVillageGameMode::OnJournalToggle()
{
        if (PanelMode == EPanelMode::Journal)
        {
                OnCancelPressed();
                return;
        }
        if (PanelMode != EPanelMode::None) { return; }
        PanelMode = EPanelMode::Journal;
        if (JournalWidget) { JournalWidget->SetVisibility(ESlateVisibility::Visible); }
        RefreshJournalUI();
}

void ATLSVillageGameMode::OnCaseFileToggle()
{
        if (PanelMode == EPanelMode::CaseFile)
        {
                OnCancelPressed();
                return;
        }
        if (PanelMode != EPanelMode::None) { return; }
        PanelMode = EPanelMode::CaseFile;
        if (CaseFileWidget) { CaseFileWidget->SetVisibility(ESlateVisibility::Visible); }
        RefreshCaseFileUI();
}

void ATLSVillageGameMode::OnBoardToggle()
{
        if (PanelMode == EPanelMode::Deduction)
        {
                OnCancelPressed();
                return;
        }
        if (PanelMode != EPanelMode::None) { return; }
        PanelMode = EPanelMode::Deduction;
        SelectedAccusationIndex = INDEX_NONE;
        bAccusationConfirmPending = false;
        if (BoardWidget) { BoardWidget->SetVisibility(ESlateVisibility::Visible); }
        RefreshBoardUI();
}

void ATLSVillageGameMode::OnCancelPressed()
{
        PanelMode = EPanelMode::None;
        bAccusationConfirmPending = false;
        if (DialogueWidget) { DialogueWidget->SetVisibility(ESlateVisibility::Hidden); }
        if (LedgerWidget) { LedgerWidget->SetVisibility(ESlateVisibility::Hidden); }
        if (JournalWidget) { JournalWidget->SetVisibility(ESlateVisibility::Hidden); }
        if (CaseFileWidget) { CaseFileWidget->SetVisibility(ESlateVisibility::Hidden); }
        if (BoardWidget) { BoardWidget->SetVisibility(ESlateVisibility::Hidden); }
}

void ATLSVillageGameMode::OnDigitPressed(int32 Digit)
{
        if (Digit < 1 || Digit > 9) { return; }
        const int32 Index = Digit - 1;

        if (PanelMode == EPanelMode::Dialogue)
        {
                // M3.8: a testimony may land inside this choice (reveal_facts
                // bridge). Snapshot the ledger so the player gets told.
                const size_t LearnedBefore = Core->Case().LearnedCount();
                std::string Entered, Err;
                if (Core->PickDialogueChoice(static_cast<size_t>(Index), Entered, Err))
                {
                        if (Core->Case().LearnedCount() > LearnedBefore && HUDWidget)
                        {
                                HUDWidget->SetToast(TEXT("Casebook: new testimony noted (press N)"));
                        }
                        if (Core->DialogueRunning()) { RefreshDialogueUI(); }
                        else { OnCancelPressed(); }
                }
                else if (HUDWidget) { HUDWidget->SetToast(UTF8_TO_TCHAR(Err.c_str())); }
                return;
        }

        // M3.8: the case file is read-only - nothing is selectable there.
        if (PanelMode == EPanelMode::CaseFile) { return; }

        // M3.8: deduction-board selection. Digits choose an accusation (or
        // form a hypothesis); E then speaks it - with the confirm step.
        if (PanelMode == EPanelMode::Deduction)
        {
                bAccusationConfirmPending = false;
                if (Index < AccusableIds.Num())
                {
                        SelectedAccusationIndex = Index;
                        bAccusationConfirmPending = true;
                        RefreshBoardUI();
                        return;
                }
                const int32 HypIndex = Index - AccusableIds.Num();
                if (HypIndex >= 0 && HypIndex < FormableHypothesisIds.Num())
                {
                        std::string Err;
                        if (Core->FormHypothesis(std::string(TCHAR_TO_UTF8(*FormableHypothesisIds[HypIndex])), Err))
                        {
                                if (HUDWidget) { HUDWidget->SetToast(TEXT("Theory pinned to the board.")); }
                        }
                        else if (HUDWidget) { HUDWidget->SetToast(UTF8_TO_TCHAR(Err.c_str())); }
                        RefreshBoardUI();
                }
                return;
        }

        if (PanelMode == EPanelMode::Table)
        {
                if (Index < SelectableEvidenceIds.Num())
                {
                        const std::string Ev = std::string(TCHAR_TO_UTF8(*SelectableEvidenceIds[Index]));
                        std::string Reveal;
                        Core->NotifyExamineEvidence(Ev, &Reveal);
                        const tls::EvidenceDef* Def = Core->Evidence().FindDef(Ev);
                        LastVerdictLine = FString::Printf(TEXT("%s\n%s"),
                                Def ? UTF8_TO_TCHAR(Def->Name.c_str()) : TEXT("?"),
                                UTF8_TO_TCHAR(Reveal.c_str()));
                        RefreshLedgerUI();
                }
                return;
        }

        if (PanelMode == EPanelMode::Board)
        {
                if (Index >= SelectableEvidenceIds.Num()) { return; }
                if (FirstSelectedIndex == INDEX_NONE)
                {
                        FirstSelectedIndex = Index;
                        RefreshLedgerUI();
                        return;
                }
                if (FirstSelectedIndex == Index)
                {
                        FirstSelectedIndex = INDEX_NONE;
                        RefreshLedgerUI();
                        return;
                }
                const std::string A = std::string(TCHAR_TO_UTF8(*SelectableEvidenceIds[FirstSelectedIndex]));
                const std::string B = std::string(TCHAR_TO_UTF8(*SelectableEvidenceIds[Index]));
                std::string Message;
                std::vector<std::string> NewInsights;
                Core->NotifyDrawLink(A, B, &Message, &NewInsights);
                LastVerdictLine = UTF8_TO_TCHAR(Message.c_str());
                FirstSelectedIndex = INDEX_NONE;
                for (const std::string& In : NewInsights)
                {
                        const tls::InsightDef* Def = Core->Evidence().FindInsight(In);
                        if (HUDWidget && Def)
                        {
                                HUDWidget->SetToast(FString::Printf(TEXT("INSIGHT: %s"), UTF8_TO_TCHAR(Def->Name.c_str())));
                        }
                }
                RefreshLedgerUI();
        }
}

void ATLSVillageGameMode::OnRestorePressed()
{
        if (PanelMode != EPanelMode::Table) { return; }
        // the slice has exactly one restorable page (EVD-TORN-PAGE)
        std::string Reveal;
        Core->NotifyRestorePage("EVD-TORN-PAGE", &Reveal);
        LastVerdictLine = UTF8_TO_TCHAR(Reveal.c_str());
        RefreshLedgerUI();
}

// ------------------------------------------------------------------ UI

void ATLSVillageGameMode::CreateWidgets()
{
        UWorld* World = GetWorld();
        if (!World) { return; }
        APlayerController* PC = World->GetFirstPlayerController();
        if (!PC) { return; }

        HUDWidget = CreateWidget<UTLSHUDWidget>(PC, UTLSHUDWidget::StaticClass());
        DialogueWidget = CreateWidget<UTLSDialogueWidget>(PC, UTLSDialogueWidget::StaticClass());
        LedgerWidget = CreateWidget<UTLSLedgerWidget>(PC, UTLSLedgerWidget::StaticClass());
        JournalWidget = CreateWidget<UTLSJournalWidget>(PC, UTLSJournalWidget::StaticClass());
        CaseFileWidget = CreateWidget<UTLSCaseFileWidget>(PC, UTLSCaseFileWidget::StaticClass());
        BoardWidget = CreateWidget<UTLSBoardWidget>(PC, UTLSBoardWidget::StaticClass());

        if (HUDWidget)
        {
                HUDWidget->AddToViewport(0);
                HUDWidget->SetVisibility(ESlateVisibility::HitTestInvisible);
        }
        if (DialogueWidget)
        {
                DialogueWidget->AddToViewport(5);
                DialogueWidget->SetVisibility(ESlateVisibility::Hidden);
        }
        if (LedgerWidget)
        {
                LedgerWidget->AddToViewport(5);
                LedgerWidget->SetVisibility(ESlateVisibility::Hidden);
        }
        if (JournalWidget)
        {
                JournalWidget->AddToViewport(5);
                JournalWidget->SetVisibility(ESlateVisibility::Hidden);
        }
        if (CaseFileWidget)
        {
                CaseFileWidget->AddToViewport(5);
                CaseFileWidget->SetVisibility(ESlateVisibility::Hidden);
        }
        if (BoardWidget)
        {
                BoardWidget->AddToViewport(5);
                BoardWidget->SetVisibility(ESlateVisibility::Hidden);
        }
}

void ATLSVillageGameMode::RefreshHUD()
{
        if (!HUDWidget) { return; }

        const FString Weather = Core->GetWeather() == tls::EWeather::Rain ? TEXT("Rain") : TEXT("Fog");
        const FString Time = UTF8_TO_TCHAR(tls::ToString(Core->GetTimeOfDay()));
        // M3.8: the case-layer keys are always discoverable on the HUD -
        // deduction-first never means interface-hidden.
        HUDWidget->SetStatusLine(FString::Printf(TEXT("Blackthorne - Day %d, %s | %s | tension %.1f | [N] case file  [B] board"),
                Core->CurrentDay(), *Time, *Weather, Core->Village().Tension()));

        // first open required objective of an active quest
        FString Objective;
        for (const tls::QuestSystem::QuestProgressLine& L : Core->Quests().ProgressLines())
        {
                if (L.bQuestActive && !L.bObjectiveDone && !L.bObjectiveOptional)
                {
                        Objective = FString::Printf(TEXT("%s: %s"), UTF8_TO_TCHAR(L.Title.c_str()), UTF8_TO_TCHAR(L.ObjectiveText.c_str()));
                        break;
                }
        }
        HUDWidget->SetObjectiveLine(Objective);

        // interaction prompt
        FString Prompt;
        if (PanelMode == EPanelMode::None)
        {
                if (ATLSInteractable* Obj = FindNearestInteractable(280.0f))
                {
                        Prompt = FString::Printf(TEXT("[E] %s"), *Obj->InteractId);
                }
                else if (ATLSNPC* Npc = FindNearestNPC(280.0f))
                {
                        Prompt = FString::Printf(TEXT("[E] Speak with %s"), *Npc->DisplayName);
                }
        }
        else if (PanelMode == EPanelMode::Dialogue)
        {
                Prompt = TEXT("1-9 choose | Esc withdraw");
        }
        else if (PanelMode == EPanelMode::Table)
        {
                Prompt = TEXT("1-9 examine | R restore the torn page | Esc leave the table");
        }
        else if (PanelMode == EPanelMode::Board)
        {
                Prompt = TEXT("1-9 pick two pages to link | Esc leave the board");
        }
        else if (PanelMode == EPanelMode::Journal)
        {
                Prompt = TEXT("J / Esc close the journal");
        }
        HUDWidget->SetPrompt(Prompt);
}

void ATLSVillageGameMode::RefreshDialogueUI()
{
        if (!DialogueWidget) { return; }
        const tls::DialogueNode* Node = Core->DialogueCurrentNode();
        if (!Node) { return; }

        const tls::NPCDef* Speaker = Core->Village().FindNpc(Node->Speaker);
        const std::string SpeakerName = Speaker ? Speaker->Name : Node->Speaker;
        bool bNeedsLesson = false;
        const std::string Rendered = Core->DialogueRenderedText(bNeedsLesson);
        FString Body = UTF8_TO_TCHAR(Rendered.c_str());
        if (bNeedsLesson) { Body += TEXT("\n(some Welsh words stay dark - Miss Vaughan keeps the lessons)"); }

        TArray<FString> ChoiceLines;
        std::vector<const tls::DialogueChoice*> Choices = Core->DialogueAvailableChoices();
        for (size_t I = 0; I < Choices.size(); ++I)
        {
                bool bLesson2 = false;
                const std::string ChoiceText = tls::RenderDialogueText(Choices[I]->Text, Core->GetWelshLevel(), bLesson2);
                const TCHAR* Prefix = TEXT("(formal) ");
                switch (Choices[I]->Tone)
                {
                case tls::ETone::Gentle: Prefix = TEXT("(gentle) "); break;
                case tls::ETone::Formal: Prefix = TEXT("(formal) "); break;
                case tls::ETone::Pressing: Prefix = TEXT("(pressing) "); break;
                case tls::ETone::Silent: Prefix = TEXT("(silent) "); break;
                }
                ChoiceLines.Add(FString::Printf(TEXT("%s%s"), Prefix, UTF8_TO_TCHAR(ChoiceText.c_str())));
        }

        DialogueWidget->SetDialogue(UTF8_TO_TCHAR(SpeakerName.c_str()), Body, ChoiceLines);
}

void ATLSVillageGameMode::RefreshLedgerUI()
{
        if (!LedgerWidget) { return; }

        SelectableEvidenceIds.Reset();

        TArray<FString> EvidenceLines;
        if (PanelMode == EPanelMode::Table)
        {
                EvidenceLines.Add(TEXT("THE FATHER'S TABLE - examine what you carry (1-9), R restores torn pages"));
                for (const std::string& Ev : Core->Evidence().CollectedIds())
                {
                        const tls::EvidenceDef* Def = Core->Evidence().FindDef(Ev);
                        const tls::EvidenceRuntime* St = Core->Evidence().State(Ev);
                        if (!Def || !St) { continue; }
                        SelectableEvidenceIds.Add(UTF8_TO_TCHAR(Ev.c_str()));
                        const int32 Index = SelectableEvidenceIds.Num();
                        EvidenceLines.Add(FString::Printf(TEXT("%d. [%s] %s%s"),
                                Index,
                                St->bExamined ? TEXT("read") : TEXT("----"),
                                UTF8_TO_TCHAR(Def->Name.c_str()),
                                (Def->bRestorable && !St->bRestored) ? TEXT("  (R: torn)") : TEXT("")));
                }
        }
        else
        {
                EvidenceLines.Add(TEXT("THE LEDGER BOARD - pick two pages (1-9) and the cord decides"));
                for (const std::string& Ev : Core->Evidence().CollectedIds())
                {
                        const tls::EvidenceDef* Def = Core->Evidence().FindDef(Ev);
                        const tls::EvidenceRuntime* St = Core->Evidence().State(Ev);
                        if (!Def || !St) { continue; }
                        SelectableEvidenceIds.Add(UTF8_TO_TCHAR(Ev.c_str()));
                        const int32 Index = SelectableEvidenceIds.Num();
                        const bool bSelected = (FirstSelectedIndex != INDEX_NONE && Index - 1 == FirstSelectedIndex);
                        EvidenceLines.Add(FString::Printf(TEXT("%d. %s%s%s"),
                                Index,
                                bSelected ? TEXT("> ") : TEXT(""),
                                UTF8_TO_TCHAR(Def->Name.c_str()),
                                St->bExamined ? TEXT("") : TEXT("  (unexamined)")));
                }
        }

        TArray<FString> LinkLines;
        for (const tls::DrawnLink& L : Core->Evidence().Links())
        {
                const tls::EvidenceDef* A = Core->Evidence().FindDef(L.A);
                const tls::EvidenceDef* B = Core->Evidence().FindDef(L.B);
                LinkLines.Add(FString::Printf(TEXT("%s %s %s : %s"),
                        A ? UTF8_TO_TCHAR(A->Name.c_str()) : UTF8_TO_TCHAR(L.A.c_str()),
                        L.bContradiction ? TEXT("=/=") : TEXT("<-->"),
                        B ? UTF8_TO_TCHAR(B->Name.c_str()) : UTF8_TO_TCHAR(L.B.c_str()),
                        UTF8_TO_TCHAR(L.Note.c_str())));
        }

        TArray<FString> InsightLines;
        InsightLines.Add(TEXT("INSIGHTS:"));
        for (const auto& KV : Core->Evidence().Insights())
        {
                if (Core->Evidence().InsightKnown(KV.first))
                {
                        InsightLines.Add(FString::Printf(TEXT("  * %s - %s"),
                                UTF8_TO_TCHAR(KV.second.Name.c_str()), UTF8_TO_TCHAR(KV.second.Description.c_str())));
                }
        }
        if (InsightLines.Num() == 1) { InsightLines.Add(TEXT("  (none yet - the cord is patient)")); }

        LedgerWidget->SetLedger(EvidenceLines, LinkLines, InsightLines,
                LastVerdictLine.IsEmpty() ? TEXT("") : FString::Printf(TEXT(">> %s"), *LastVerdictLine));
}

void ATLSVillageGameMode::RefreshJournalUI()
{
        if (!JournalWidget) { return; }

        TArray<FString> QuestLines;
        QuestLines.Add(TEXT("THE FILE (quests):"));
        for (const tls::QuestSystem::QuestProgressLine& L : Core->Quests().ProgressLines())
        {
                QuestLines.Add(FString::Printf(TEXT("  %s%s - %s%s"),
                        L.bObjectiveDone ? TEXT("[x] ") : TEXT("[ ] "),
                        UTF8_TO_TCHAR(L.Title.c_str()),
                        UTF8_TO_TCHAR(L.ObjectiveText.c_str()),
                        L.bObjectiveOptional ? TEXT("  (optional)") : TEXT("")));
        }

        TArray<FString> DiaryLines;
        DiaryLines.Add(TEXT("EDMUND'S JOURNAL:"));
        for (const tls::Game::JournalEntry& E : Core->Journal())
        {
                DiaryLines.Add(FString::Printf(TEXT("  Day %d - %s"), E.Day, UTF8_TO_TCHAR(E.Text.c_str())));
        }

        JournalWidget->SetJournal(QuestLines, DiaryLines);
}

// ------------------------------------------------------------------ M3.8 case layer

FString ATLSVillageGameMode::NpcDisplayName(const std::string& NpcId) const
{
        // Schedule/sim names are canon (sim_blackthorne); the raw id is the
        // honest fallback for any dossier entry outside the sim registry.
        if (const tls::NPCDef* Npc = Core->Village().FindNpc(NpcId))
        {
                return ToFString(Npc->Name);
        }
        return ToFString(NpcId);
}

void ATLSVillageGameMode::RefreshCaseFileUI()
{
        if (!CaseFileWidget) { return; }

        // --- testimonies: only what Edmund actually heard, in the order
        // heard. Stance/origin/reliability come from the heard account; the
        // canonical truth summaries are NEVER shown (pillar B).
        TArray<FString> TestimonyLines;
        TestimonyLines.Add(TEXT("THE CASE FILE (what you have been told):"));
        const std::vector<tls::HeardTestimony> Heard = Core->Case().HeardList();
        if (Heard.empty())
        {
                TestimonyLines.Add(TEXT("  (no testimony yet - the village has not spoken to you)"));
        }
        for (const tls::HeardTestimony& H : Heard)
        {
                const tls::CaseFactDef* Fact = Core->Case().FindFact(H.FactId);
                const tls::TestimonyDef* T = Core->Case().FindTestimony(H.FactId, H.NpcId);
                if (!Fact || !T) { continue; }
                FString Line = FString::Printf(TEXT("  Day %d, %02d:00 - %s on %s (%s, %s, weight %.2f): %s"),
                        H.Day, H.Hour,
                        *NpcDisplayName(H.NpcId), *ToFString(Fact->Topic),
                        UTF8_TO_TCHAR(tls::ToString(T->Stance)),
                        UTF8_TO_TCHAR(tls::ToString(T->Origin)),
                        T->Reliability,
                        *ToFString(T->Stance == tls::ETestimonyStance::Claims ? T->ClaimText : T->Account));
                TestimonyLines.Add(Line);
                if (T->bDeliberate && !T->LieReason.empty())
                {
                        TestimonyLines.Add(FString::Printf(TEXT("      (a lie - and you can feel it: %s)"), *ToFString(T->LieReason)));
                }
        }

        // --- dossiers: public motive and fear are always shown; the deep
        // motive only once every secret the NPC keeps has been earned;
        // unlearned secrets read as "keeps something back" - never the truth.
        TArray<FString> DossierLines;
        DossierLines.Add(TEXT("THE PARISH (what you know of its people):"));
        for (const auto& KV : Core->Case().Dossiers())
        {
                const tls::DossierDef& D = KV.second;
                bool bAllSecretsEarned = !D.SecretFacts.empty();
                for (const std::string& F : D.SecretFacts)
                {
                        if (!Core->Case().IsLearned(F)) { bAllSecretsEarned = false; break; }
                }
                DossierLines.Add(FString::Printf(TEXT("  %s - motive: %s | fears: %s"),
                        *NpcDisplayName(D.NpcId),
                        *ToFString(D.PublicMotive), *ToFString(D.Fear)));
                for (const std::string& F : D.SecretFacts)
                {
                        DossierLines.Add(Core->Case().IsLearned(F)
                                ? FString::Printf(TEXT("      secret learned: %s"), *ToFString(F))
                                : TEXT("      keeps something back..."));
                }
                if (bAllSecretsEarned && !D.DeepMotive.empty())
                {
                        DossierLines.Add(FString::Printf(TEXT("      what truly drives them: %s"), *ToFString(D.DeepMotive)));
                }
        }

        CaseFileWidget->SetCaseFile(TestimonyLines, DossierLines,
                TEXT("N - close the case file   |   B - the deduction board   |   Esc - back to the street"));
}

void ATLSVillageGameMode::RefreshBoardUI()
{
        if (!BoardWidget) { return; }

        // Accusation ids are computed FIRST so the formable-theory digits
        // always start after them (the arrays are rebuilt on every refresh -
        // no stale digit layout from the previous open).
        AccusableIds.Reset();
        for (const auto& AccKV : Core->Deduction().Accusations())
        {
                AccusableIds.Add(ToFString(AccKV.second.Id));
        }

        // --- hypotheses: formed ones with their live verdict; unformed ones
        // are listed as formable theories. Requirements are NEVER listed -
        // the open-questions shelf is the fair signal, not a checklist.
        TArray<FString> HypothesisLines;
        HypothesisLines.Add(TEXT("HYPOTHESES (your own constructions):"));
        FormableHypothesisIds.Reset();
        const int32 HypDigitBase = AccusableIds.Num();
        for (const auto& KV : Core->Deduction().Hypotheses())
        {
                const tls::HypothesisDef& Def = KV.second;
                const tls::FormedHypothesis* Formed = Core->Deduction().Formed(Def.Id);
                if (Formed)
                {
                        const TCHAR* Verdict = nullptr;
                        switch (Formed->Verdict)
                        {
                        case tls::EHypothesisVerdict::Supported: Verdict = TEXT("SUPPORTED by the evidence"); break;
                        case tls::EHypothesisVerdict::Partial:   Verdict = TEXT("PARTIAL - some weight, not enough"); break;
                        case tls::EHypothesisVerdict::Refuted:   Verdict = TEXT("REFUTED - and it stays refuted"); break;
                        default:                                 Verdict = TEXT("unsupported so far"); break;
                        }
                        HypothesisLines.Add(FString::Printf(TEXT("  %s - %s"), *ToFString(Def.Title), Verdict));
                        if (Formed->Verdict == tls::EHypothesisVerdict::Refuted && !Formed->RefuteReason.empty())
                        {
                                HypothesisLines.Add(FString::Printf(TEXT("      why it fell: %s"), *ToFString(Formed->RefuteReason)));
                        }
                }
                else
                {
                        FormableHypothesisIds.Add(ToFString(Def.Id));
                        HypothesisLines.Add(FString::Printf(TEXT("  [pin as theory: %d]  %s"), HypDigitBase + FormableHypothesisIds.Num(), *ToFString(Def.Title)));
                }
        }

        // --- open questions: the shelf of what is still missing
        TArray<FString> QuestionLines;
        QuestionLines.Add(TEXT("OPEN QUESTIONS (what the board still lacks):"));
        const std::vector<tls::OpenQuestion> Questions = Core->OpenQuestions();
        if (Questions.empty())
        {
                QuestionLines.Add(TEXT("  (none pinned - form a theory to see what it needs)"));
        }
        for (const tls::OpenQuestion& Q : Questions)
        {
                QuestionLines.Add(FString::Printf(TEXT("  ? %s"), *ToFString(Q.Question)));
        }

        // --- contradictions: only among accounts the player could have heard
        TArray<FString> ConflictLines;
        ConflictLines.Add(TEXT("CONTRADICTIONS (accounts that cannot both stand):"));
        bool bAnyConflict = false;
        for (const auto& KV : Core->Case().Facts())
        {
                if (!Core->Case().IsLearned(KV.first)) { continue; }
                for (const tls::CaseFactSystem::FactConflict& C : Core->Case().FindConflicts(KV.first, *Core))
                {
                        bAnyConflict = true;
                        ConflictLines.Add(FString::Printf(TEXT("  %s vs %s on %s - %s"),
                                *NpcDisplayName(C.NpcA), *NpcDisplayName(C.NpcB), *ToFString(C.FactId), *ToFString(C.Reason)));
                }
        }
        if (!bAnyConflict)
        {
                ConflictLines.Add(TEXT("  (no contradiction has surfaced yet)"));
        }

        // --- accusations: speakable always; the tier preview is the honest
        // strength of the player's own case, never the hidden truth
        TArray<FString> AccusationLines;
        AccusationLines.Add(TEXT("ACCUSATIONS (words, once said, cannot be unsaid):"));
        for (const auto& KV : Core->Deduction().Accusations())
        {
                const tls::AccusationDef& Def = KV.second;
                AccusableIds.Add(ToFString(Def.Id));
                const int32 Digit = AccusableIds.Num();
                const bool bSpoken = Core->Deduction().AccusedBefore(Def.Id) && !Def.bRepeatable;
                tls::EAccusationTier Tier;
                const bool bKnown = Core->PreviewAccusationTier(Def.Id, Tier);
                const TCHAR* TierText = !bKnown ? TEXT("?")
                        : Tier == tls::EAccusationTier::Grounded ? TEXT("your case STANDS firmly (grounded)")
                        : Tier == tls::EAccusationTier::Partial ? TEXT("your case is THIN (partial)")
                        : TEXT("your case has NO ground (baseless)");
                AccusationLines.Add(FString::Printf(TEXT("  [select: %d]  %s - %s%s"), Digit,
                        *ToFString(Def.TargetLabel), TierText,
                        bSpoken ? TEXT("  (already said)") : TEXT("")));
        }

        // --- status line: selection / confirm / result feedback
        FString Status;
        if (bAccusationConfirmPending && AccusableIds.IsValidIndex(SelectedAccusationIndex))
        {
                // the ids were built from the live defs this refresh, so the
                // lookup cannot miss - the guard keeps a stale index honest
                if (const tls::AccusationDef* Pending =
                        Core->Deduction().FindAccusation(std::string(TCHAR_TO_UTF8(*AccusableIds[SelectedAccusationIndex]))))
                {
                        Status = FString::Printf(TEXT("Speak it?  \"%s\"   E - say it   Esc or another digit - hold your tongue"),
                                *ToFString(Pending->TargetLabel));
                }
        }
        else if (!LastVerdictLine.IsEmpty())
        {
                Status = LastVerdictLine;
        }
        else
        {
                Status = TEXT("digits - select an accusation or pin a theory   |   E - speak the selected accusation   |   Esc - back");
        }

        BoardWidget->SetBoard(HypothesisLines, QuestionLines, ConflictLines, AccusationLines, Status);
}

void ATLSVillageGameMode::ConfirmAccusation()
{
        if (PanelMode != EPanelMode::Deduction) { return; }
        if (!bAccusationConfirmPending || !AccusableIds.IsValidIndex(SelectedAccusationIndex))
        {
                LastVerdictLine = TEXT("Nothing chosen to say. Digits select; E speaks.");
                RefreshBoardUI();
                return;
        }

        const std::string AccId = std::string(TCHAR_TO_UTF8(*AccusableIds[SelectedAccusationIndex]));
        tls::EAccusationTier Tier;
        std::string Err;
        if (!Core->MakeAccusation(AccId, Tier, Err))
        {
                LastVerdictLine = FString::Printf(TEXT("The words will not come: %s"), UTF8_TO_TCHAR(Err.c_str()));
                bAccusationConfirmPending = false;
                RefreshBoardUI();
                return;
        }

        // The tier decides the village's answer - shown plainly, kept in the
        // journal by the core. Consequences (trust/tension/reputation) have
        // already landed inside MakeAccusation.
        const tls::AccusationDef* Def = Core->Deduction().FindAccusation(AccId);
        const TCHAR* TierText = Tier == tls::EAccusationTier::Grounded ? TEXT("GROUNDED")
                : Tier == tls::EAccusationTier::Partial ? TEXT("PARTIAL") : TEXT("BASELESS");
        LastVerdictLine = FString::Printf(TEXT("Said aloud (%s): "%s""), TierText,
                Def ? *ToFString(Def->TargetLabel) : TEXT("?"));
        if (HUDWidget)
        {
                HUDWidget->SetToast(LastVerdictLine);
                if (Def && !Def->OnGrounded.JournalNote.empty() && Tier == tls::EAccusationTier::Grounded)
                {
                        HUDWidget->SetToast(ToFString(Def->OnGrounded.JournalNote));
                }
        }
        bAccusationConfirmPending = false;
        SelectedAccusationIndex = INDEX_NONE;
        RefreshBoardUI();
}

// ------------------------------------------------------------------ day / weather

void ATLSVillageGameMode::ApplyDayPresentation()
{
        const bool bRain = Core->GetWeather() == tls::EWeather::Rain;

        if (SunLight)
        {
                FRotator SunRotation(-35.0f, 45.0f, 0.0f);
                float Intensity = 2.2f;
                switch (Core->GetTimeOfDay())
                {
                case tls::ETimeOfDay::Morning:  SunRotation = FRotator(-35.0f, 45.0f, 0.0f); break;
                case tls::ETimeOfDay::Noon:     SunRotation = FRotator(-60.0f, 90.0f, 0.0f); break;
                case tls::ETimeOfDay::Afternoon:SunRotation = FRotator(-40.0f, 210.0f, 0.0f); break;
                case tls::ETimeOfDay::Evening:  SunRotation = FRotator(-12.0f, 265.0f, 0.0f); Intensity = 1.1f; break;
                case tls::ETimeOfDay::Night:    SunRotation = FRotator(25.0f, 300.0f, 0.0f); Intensity = 0.35f; break;
                }
                if (bRain) { Intensity *= 0.5f; }
                if (ULightComponent* LightComp = SunLight->GetLightComponent())
                {
                        LightComp->SetWorldRotation(SunRotation);
                        LightComp->Intensity = Intensity;
                }
        }

        if (HeightFog)
        {
                if (UExponentialHeightFogComponent* FogComp = HeightFog->GetComponent())
                {
                        FogComp->SetFogDensity(bRain ? 0.08f : 0.25f);
                }
        }

        if (Audio)
        {
                Audio->SetWeatherBlend(bRain ? 1.0f : 0.0f);
        }
}

void ATLSVillageGameMode::AdvanceDay()
{
        std::string Reason;
        if (!Core->NotifySleep(Reason))
        {
                if (HUDWidget) { HUDWidget->SetToast(UTF8_TO_TCHAR(Reason.c_str())); }
                return;
        }

        // day 2 world state: mill scene spawns, villagers move to tension posts
        SpawnInteractables(true);
        for (ATLSNPC* Npc : Villagers)
        {
                if (!Npc) { continue; }
                const std::string NpcId(TCHAR_TO_UTF8(*Npc->NpcId));
                const std::string Zone = Core->Village().NpcZoneAt(NpcId, Core->Village().Hour());
                if (FVector* Center = AreaCenters.Find(UTF8_TO_TCHAR(Zone.c_str())))
                {
                        Npc->SetActorLocation(*Center + FVector(0.0f, 0.0f, 20.0f));
                }
        }

        ApplyDayPresentation();
        RefreshHUD();
        RefreshJournalUI();
        if (HUDWidget)
        {
                HUDWidget->SetToast(FString::Printf(TEXT("Day %d. %s"),
                        Core->CurrentDay(),
                        Core->GetWeather() == tls::EWeather::Rain ? TEXT("Rain comes off the hills.") : TEXT("The fog holds.")));
        }
}

// ------------------------------------------------------------------ save

void ATLSVillageGameMode::SaveAtDesk()
{
        const std::string Payload = Core->SaveToString();
        if (TLSSave::WriteSlot(FString(UTF8_TO_TCHAR(Payload.c_str())), Core->CurrentDay()))
        {
                if (HUDWidget)
                {
                        HUDWidget->SetToast(FString::Printf(TEXT("The day's work is safe. (Day %d saved at the desk.)"), Core->CurrentDay()));
                }
        }
        else if (HUDWidget)
        {
                HUDWidget->SetToast(TEXT("The desk drawer jams - save failed (see log)."));
        }
}

void ATLSVillageGameMode::TryContinueFromSlot()
{
        FString Payload;
        int32 Day = 1;
        if (TLSSave::ReadSlot(Payload, Day))
        {
                std::string Err;
                if (Core->LoadFromString(std::string(TCHAR_TO_UTF8(*Payload)), Err))
                {
                        if (HUDWidget)
                        {
                                HUDWidget->SetToast(FString::Printf(TEXT("The desk remembers: Day %d."), Day));
                        }
                        return;
                }
                UE_LOG(LogTemp, Warning, TEXT("[TLS] Save slot unreadable (%s) - starting fresh."), UTF8_TO_TCHAR(Err.c_str()));
        }
}

void ATLSVillageGameMode::TLSNewGame()
{
        Core->NewGame();
        // reset slice-local state so day-1 story beats (the burial bell) can
        // happen again on the fresh run
        bBellRung = false;
        FirstSelectedIndex = INDEX_NONE;
        LastVerdictLine.Reset();
        SpawnInteractables(false);
        ApplyDayPresentation();
        RefreshHUD();
        RefreshJournalUI();
        if (HUDWidget) { HUDWidget->SetToast(TEXT("A fresh page. Day 1.")); }
}
