// THE LAST SIN: The Sin-Eater - M0
// TLSGameMode: builds the grey-box test room at runtime, places the imported
// calibration assets (SM_TLS-ENV-001 / SM_TLS-ENV-002) and runs the in-game
// CAL-01 measurement checks (axis & scale contract, TECHNICAL_PIPELINE 4/9).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "TLSGameMode.generated.h"

UCLASS()
class TLS_API ATLSGameMode : public AGameModeBase
{
        GENERATED_BODY()

public:
        ATLSGameMode();

protected:
        virtual void StartPlay() override;

private:
        /** Grey-box room: 20 m x 20 m floor, 3 m walls, collision test blocks, sun. */
        void BuildTestRoom();

        /** Places the imported calibration meshes at floor level (pivot-at-origin contract). */
        void SpawnCalibrationMeshes();

        /** Measures imported mesh bounds against the CAL-01 contract and logs + writes a JSON report. */
        void RunCalibrationChecks();

        /** True when 03_Unreal/Scripts/02_import_and_calibrate.bat has been run (assets exist). */
        bool GetCalibrationMeshes(class UStaticMesh*& OutGnomon, class UStaticMesh*& OutFigure) const;

        /** Deferred-spawns a scaled box built from the given engine mesh (cube or calibration mesh). */
        class AStaticMeshActor* SpawnBoxActor(class UStaticMesh* Mesh, const FVector& Center, const FVector& Scale, const TCHAR* Label);

        /** Single numeric comparison with percentage tolerance; logs [CAL-01] PASS/FAIL and appends a JSON line. */
        bool CheckDimension(const FString& CheckName, float Measured, float Expected, TArray<FString>& Report);

        /** Writes 03_Unreal/Reports/calibration_ingame.json (UTF-8). */
        void WriteInGameReport(const TArray<FString>& Lines, bool bOverallPass);
};
