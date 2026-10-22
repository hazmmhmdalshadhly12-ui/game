// THE LAST SIN: The Sin-Eater - M0

#include "TLSGameMode.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "TLSCharacter.h"

namespace TLSM0
{
        // CAL-01 contract values (centimetres) - docs/TECHNICAL_PIPELINE.md sections 4 and 9,
        // cross-checked against the verified generator output
        // (02_Art/exports/manifest_calibration.json: gnomon bbox -50..85 / -50..50 / 0..77,
        // figure height 0..175, material slots 5 / 1).
        constexpr float GnomonXSize = 135.0f;   // 1.00 m plate + 0.35 m arrow pointing +X
        constexpr float GnomonYSize = 100.0f;   // calibration base plate
        constexpr float GnomonZSize = 77.0f;    // plate + body + spire
        constexpr float GnomonXMin  = -50.0f;
        constexpr float GnomonXMax  = 85.0f;    // arrow tip beyond the +X face (forward proof)
        constexpr float GnomonYMin  = -50.0f;
        constexpr float GnomonYMax  = 50.0f;
        constexpr float GnomonZMin  = 0.0f;     // pivot at origin (base on the floor)
        constexpr float GnomonZMax  = 77.0f;
        constexpr int32 GnomonMaterialSlots = 5;   // Base, Body, AxisX, AxisY, AxisZ

        constexpr float FigureXSize = 57.0f;    // arm span (arm cylinders reach +-0.285 m)
        constexpr float FigureYSize = 25.0f;     // head diameter (r 0.125 m, wider than the flattened torso)
        constexpr float FigureZSize = 175.0f;   // canonical human reference height
        constexpr float FigureZMin  = 0.0f;     // pivot at the feet
        constexpr int32 FigureMaterialSlots = 1;

        constexpr float TolerancePct = 0.5f;    // CAL-01 acceptance: <= 0.5% (MILESTONE_PLAN M0)

        const TCHAR* GnomonAssetPath = TEXT("/Game/TLS/ENV/TLS-ENV-001/SM_TLS-ENV-001.SM_TLS-ENV-001");
        const TCHAR* FigureAssetPath = TEXT("/Game/TLS/ENV/TLS-ENV-002/SM_TLS-ENV-002.SM_TLS-ENV-002");
}

ATLSGameMode::ATLSGameMode()
{
        DefaultPawnClass = ATLSCharacter::StaticClass();
}

void ATLSGameMode::StartPlay()
{
        Super::StartPlay();

        // The generated test map is intentionally EMPTY (no PlayerStart), so a pawn
        // may not exist yet on very first play. Guarantee one at the room centre.
        if (UWorld* World = GetWorld())
        {
                for (FConstControllerIterator It = World->GetControllerIterator(); It; ++It)
                {
                        if (APlayerController* PC = Cast<APlayerController>(*It))
                        {
                                if (!PC->GetPawn())
                                {
                                        RestartPlayerAtTransform(PC, FTransform(FRotator::ZeroRotator, FVector(0.0f, 0.0f, 100.0f)));
                                }
                        }
                }
        }

        BuildTestRoom();
        SpawnCalibrationMeshes();
        RunCalibrationChecks();
}

void ATLSGameMode::BuildTestRoom()
{
        UWorld* World = GetWorld();
        if (!World)
        {
                return;
        }

        UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
        if (!Cube)
        {
                UE_LOG(LogTemp, Error, TEXT("[M0] Engine basic cube mesh not found - test room NOT built."));
                return;
        }

        // Floor: 20 m x 20 m, top surface exactly at Z = 0.
        SpawnBoxActor(Cube, FVector(0.0f, 0.0f, -5.0f), FVector(20.0f, 20.0f, 0.1f), TEXT("M0_Floor"));

        // Perimeter walls: 20 m long, 3 m high, 20 cm thick.
        SpawnBoxActor(Cube, FVector(0.0f, 1000.0f, 150.0f), FVector(20.0f, 0.2f, 3.0f), TEXT("M0_Wall_North"));
        SpawnBoxActor(Cube, FVector(0.0f, -1000.0f, 150.0f), FVector(20.0f, 0.2f, 3.0f), TEXT("M0_Wall_South"));
        SpawnBoxActor(Cube, FVector(1000.0f, 0.0f, 150.0f), FVector(0.2f, 20.0f, 3.0f), TEXT("M0_Wall_East"));
        SpawnBoxActor(Cube, FVector(-1000.0f, 0.0f, 150.0f), FVector(0.2f, 20.0f, 3.0f), TEXT("M0_Wall_West"));

        // Collision / scale test blocks (walk around them, crouch behind the 50 cm one).
        SpawnBoxActor(Cube, FVector(300.0f, 400.0f, 50.0f),    FVector(1.0f, 1.0f, 1.0f), TEXT("M0_Block_100cm"));
        SpawnBoxActor(Cube, FVector(-350.0f, 200.0f, 25.0f),   FVector(0.5f, 0.5f, 0.5f), TEXT("M0_Block_50cm"));
        SpawnBoxActor(Cube, FVector(400.0f, -300.0f, 100.0f),  FVector(1.0f, 1.0f, 2.0f), TEXT("M0_Block_200cm_Tall"));

        // Sun (movable so it registers safely after world begin-play).
        const FTransform SunTransform(FRotator(-45.0f, 30.0f, 0.0f), FVector(0.0f, 0.0f, 500.0f));
        ADirectionalLight* Sun = World->SpawnActorDeferred<ADirectionalLight>(
                ADirectionalLight::StaticClass(), SunTransform, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (Sun)
        {
                if (ULightComponent* LightComp = Sun->GetLightComponent())
                {
                        LightComp->SetMobility(EComponentMobility::Movable);
                        LightComp->Intensity = 3.5f;
                }
                Sun->FinishSpawning(SunTransform);
        }

        UE_LOG(LogTemp, Log, TEXT("[M0] Test room built: 20m x 20m floor, 3m walls, 3 collision blocks, movable sun (Lumen)."));
}

AStaticMeshActor* ATLSGameMode::SpawnBoxActor(UStaticMesh* Mesh, const FVector& Center, const FVector& Scale, const TCHAR* Label)
{
        UWorld* World = GetWorld();
        if (!World || !Mesh)
        {
                return nullptr;
        }

        const FTransform BoxTransform(FQuat::Identity, Center);
        AStaticMeshActor* Actor = World->SpawnActorDeferred<AStaticMeshActor>(
                AStaticMeshActor::StaticClass(), BoxTransform, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
        if (!Actor)
        {
                return nullptr;
        }

        UStaticMeshComponent* Comp = Actor->GetStaticMeshComponent();
        Comp->SetStaticMesh(Mesh);
        Comp->SetMobility(EComponentMobility::Movable);
        Comp->SetRelativeScale3D(Scale);
        Actor->FinishSpawning(BoxTransform);

        UE_LOG(LogTemp, Log, TEXT("[M0] Spawned %s at (%.0f, %.0f, %.0f)."),
                Label, Center.X, Center.Y, Center.Z);
        return Actor;
}

bool ATLSGameMode::GetCalibrationMeshes(UStaticMesh*& OutGnomon, UStaticMesh*& OutFigure) const
{
        OutGnomon = LoadObject<UStaticMesh>(nullptr, TLSM0::GnomonAssetPath);
        OutFigure = LoadObject<UStaticMesh>(nullptr, TLSM0::FigureAssetPath);
        return OutGnomon != nullptr && OutFigure != nullptr;
}

void ATLSGameMode::SpawnCalibrationMeshes()
{
        UStaticMesh* Gnomon = nullptr;
        UStaticMesh* Figure = nullptr;
        if (!GetCalibrationMeshes(Gnomon, Figure))
        {
                UE_LOG(LogTemp, Error, TEXT("[CAL-01] Calibration meshes not found under /Game/TLS/ENV/."));
                UE_LOG(LogTemp, Error, TEXT("[CAL-01] Run 03_Unreal/Scripts/02_import_and_calibrate.bat first (imports the two FBX files)."));
                return;
        }

        // Pivot-at-origin contract: placing at Z = 0 puts the base / feet on the floor.
        SpawnBoxActor(Gnomon, FVector(-300.0f, -600.0f, 0.0f), FVector(1.0f), TEXT("M0_Calibration_Gnomon"));
        SpawnBoxActor(Figure, FVector(200.0f, -600.0f, 0.0f),  FVector(1.0f), TEXT("M0_Calibration_Figure"));
        UE_LOG(LogTemp, Log, TEXT("[M0] Calibration assets placed: gnomon at (-300,-600,0), figure at (200,-600,0)."));
}

bool ATLSGameMode::CheckDimension(const FString& CheckName, float Measured, float Expected, TArray<FString>& Report)
{
        const float Tolerance = FMath::Abs(Expected) * TLSM0::TolerancePct / 100.0f;
        const bool bPassed = FMath::Abs(Measured - Expected) <= Tolerance;

        const FString Line = FString::Printf(TEXT("[CAL-01] %s : %s - %.3f cm (expected %.3f +/- %.3f)"),
                bPassed ? TEXT("PASS") : TEXT("FAIL"), *CheckName, Measured, Expected, Tolerance);
        if (bPassed)
        {
                UE_LOG(LogTemp, Log, TEXT("%s"), *Line);
        }
        else
        {
                UE_LOG(LogTemp, Error, TEXT("%s"), *Line);
        }

        Report.Add(FString::Printf(TEXT("    \"%s\": {\"measured_cm\": %.3f, \"expected_cm\": %.3f, \"tolerance_cm\": %.3f, \"pass\": %s}"),
                *CheckName, Measured, Expected, Tolerance, bPassed ? TEXT("true") : TEXT("false")));
        return bPassed;
}

void ATLSGameMode::RunCalibrationChecks()
{
        UStaticMesh* Gnomon = nullptr;
        UStaticMesh* Figure = nullptr;
        if (!GetCalibrationMeshes(Gnomon, Figure))
        {
                UE_LOG(LogTemp, Error, TEXT("[CAL-01] SKIPPED - calibration assets are not imported yet (no fabricated results)."));
                return;
        }

        TArray<FString> Report;
        bool bOverall = true;

        // ---------------- TLS-ENV-001 (gnomon) ----------------
        const FBox G = Gnomon->GetBounds();
        const FVector GSize = G.GetSize();
        Report.Add(FString::Printf(TEXT("    \"gnomon_bounds_cm\": {\"min\": [%.3f, %.3f, %.3f], \"max\": [%.3f, %.3f, %.3f]}"),
                G.Min.X, G.Min.Y, G.Min.Z, G.Max.X, G.Max.Y, G.Max.Z));

        bOverall &= CheckDimension(TEXT("gnomon overall X size (plate 100 + arrow 35)"), GSize.X, TLSM0::GnomonXSize, Report);
        bOverall &= CheckDimension(TEXT("gnomon overall Y size (base plate)"), GSize.Y, TLSM0::GnomonYSize, Report);
        bOverall &= CheckDimension(TEXT("gnomon overall Z size"), GSize.Z, TLSM0::GnomonZSize, Report);
        bOverall &= CheckDimension(TEXT("gnomon X min (back face of plate)"), G.Min.X, TLSM0::GnomonXMin, Report);
        bOverall &= CheckDimension(TEXT("gnomon X max (arrow tip, forward +X)"), G.Max.X, TLSM0::GnomonXMax, Report);
        bOverall &= CheckDimension(TEXT("gnomon Y min"), G.Min.Y, TLSM0::GnomonYMin, Report);
        bOverall &= CheckDimension(TEXT("gnomon Y max"), G.Max.Y, TLSM0::GnomonYMax, Report);
        bOverall &= CheckDimension(TEXT("gnomon Z min (pivot at origin)"), G.Min.Z, TLSM0::GnomonZMin, Report);
        bOverall &= CheckDimension(TEXT("gnomon Z max (spire top)"), G.Max.Z, TLSM0::GnomonZMax, Report);

        // Forward-axis proof: the arrow extends +X beyond the symmetric plate.
        const bool bForwardX = (G.Max.X > 50.0f + 25.0f) && (FMath::Abs(G.Min.X) < 50.0f + 1.0f);
        if (bForwardX)
        {
                UE_LOG(LogTemp, Log, TEXT("[CAL-01] PASS : gnomon forward axis = +X - X range [%.2f .. %.2f]"), G.Min.X, G.Max.X);
        }
        else
        {
                UE_LOG(LogTemp, Error, TEXT("[CAL-01] FAIL : gnomon forward axis = +X - X range [%.2f .. %.2f]"), G.Min.X, G.Max.X);
        }
        Report.Add(FString::Printf(TEXT("    \"gnomon_forward_plus_x\": {\"x_min\": %.3f, \"x_max\": %.3f, \"pass\": %s}"),
                G.Min.X, G.Max.X, bForwardX ? TEXT("true") : TEXT("false")));
        bOverall &= bForwardX;

        const int32 GSlots = Gnomon->GetStaticMaterials().Num();
        const bool bGSlots = GSlots == TLSM0::GnomonMaterialSlots;
        if (bGSlots)
        {
                UE_LOG(LogTemp, Log, TEXT("[CAL-01] PASS : gnomon material slots - %d (expected %d)"), GSlots, TLSM0::GnomonMaterialSlots);
        }
        else
        {
                UE_LOG(LogTemp, Error, TEXT("[CAL-01] FAIL : gnomon material slots - %d (expected %d)"), GSlots, TLSM0::GnomonMaterialSlots);
        }
        Report.Add(FString::Printf(TEXT("    \"gnomon_material_slots\": {\"measured\": %d, \"expected\": %d, \"pass\": %s}"),
                GSlots, TLSM0::GnomonMaterialSlots, bGSlots ? TEXT("true") : TEXT("false")));
        bOverall &= bGSlots;

        // ---------------- TLS-ENV-002 (reference figure) ----------------
        const FBox FBoxLocal = Figure->GetBounds();
        const FVector FSize = FBoxLocal.GetSize();
        Report.Add(FString::Printf(TEXT("    \"figure_bounds_cm\": {\"min\": [%.3f, %.3f, %.3f], \"max\": [%.3f, %.3f, %.3f]}"),
                FBoxLocal.Min.X, FBoxLocal.Min.Y, FBoxLocal.Min.Z, FBoxLocal.Max.X, FBoxLocal.Max.Y, FBoxLocal.Max.Z));

        bOverall &= CheckDimension(TEXT("figure height (canonical 1.75 m)"), FSize.Z, TLSM0::FigureZSize, Report);
        bOverall &= CheckDimension(TEXT("figure arm span X"), FSize.X, TLSM0::FigureXSize, Report);
        bOverall &= CheckDimension(TEXT("figure depth Y"), FSize.Y, TLSM0::FigureYSize, Report);
        bOverall &= CheckDimension(TEXT("figure Z min (pivot at feet)"), FBoxLocal.Min.Z, TLSM0::FigureZMin, Report);

        const int32 FSlots = Figure->GetStaticMaterials().Num();
        const bool bFSlots = FSlots == TLSM0::FigureMaterialSlots;
        if (bFSlots)
        {
                UE_LOG(LogTemp, Log, TEXT("[CAL-01] PASS : figure material slots - %d (expected %d)"), FSlots, TLSM0::FigureMaterialSlots);
        }
        else
        {
                UE_LOG(LogTemp, Error, TEXT("[CAL-01] FAIL : figure material slots - %d (expected %d)"), FSlots, TLSM0::FigureMaterialSlots);
        }
        Report.Add(FString::Printf(TEXT("    \"figure_material_slots\": {\"measured\": %d, \"expected\": %d, \"pass\": %s}"),
                FSlots, TLSM0::FigureMaterialSlots, bFSlots ? TEXT("true") : TEXT("false")));
        bOverall &= bFSlots;

        UE_LOG(LogTemp, Log, TEXT("[CAL-01] OVERALL (in-game): %s"), bOverall ? TEXT("PASS") : TEXT("FAIL"));

        WriteInGameReport(Report, bOverall);
}

void ATLSGameMode::WriteInGameReport(const TArray<FString>& Lines, bool bOverallPass)
{
        const FString ReportDir = FPaths::ProjectDir() / TEXT("Reports");
        IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
        PlatformFile.CreateDirectoryTree(*ReportDir);

        const FString ReportPath = ReportDir / TEXT("calibration_ingame.json");
        const FString Content = FString::Printf(
                TEXT("{\n  \"stage\": \"M0 - CAL-01 in-game measurement\",\n  \"overall_pass\": %s,\n  \"tolerance_pct\": %.2f,\n  \"checks\": {\n%s\n  }\n}\n"),
                bOverallPass ? TEXT("true") : TEXT("false"), TLSM0::TolerancePct,
                *FString::Join(Lines, TEXT(",\n")));

        if (FFileHelper::SaveStringToFile(Content, *ReportPath, FFileHelper::EEncodingOptions::ForceUTF8))
        {
                UE_LOG(LogTemp, Log, TEXT("[CAL-01] In-game report written: %s"), *ReportPath);
        }
        else
        {
                UE_LOG(LogTemp, Error, TEXT("[CAL-01] Failed to write in-game report: %s"), *ReportPath);
        }
}
