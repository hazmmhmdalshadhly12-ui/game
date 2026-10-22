// THE LAST SIN: The Sin-Eater - M1
// TLSNPC.cpp

#include "TLSNPC.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"

ATLSNPC::ATLSNPC()
{
        PrimaryActorTick.bCanEverTick = false;

        RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

        BodyVisual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
        BodyVisual->SetupAttachment(RootComponent);
        BodyVisual->SetMobility(EComponentMobility::Movable);

        NameLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Name"));
        NameLabel->SetupAttachment(RootComponent);
        NameLabel->SetRelativeLocation(FVector(0.0f, 0.0f, 230.0f));
        NameLabel->SetHorizontalAlignment(EHTA_Center);
        NameLabel->SetTextRenderColor(FColor::FromHex("D9CBB2"));
        NameLabel->SetWorldSize(14.0f);
        NameLabel->SetVisibility(true);
}

void ATLSNPC::SetBlockoutColor(const FColor& Color)
{
        if (!GetWorld() || !BodyVisual) { return; }

        UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
        if (Cylinder)
        {
                BodyVisual->SetStaticMesh(Cylinder);
                BodyVisual->SetRelativeScale3D(FVector(0.35f, 0.35f, 0.9f));   // ~175 cm tall, slim
                BodyVisual->SetRelativeLocation(FVector(0.0f, 0.0f, 90.0f));
        }

        UMaterialInterface* BaseMaterial = LoadObject<UMaterialInterface>(
                nullptr, TEXT("/Game/TLS/Materials/M_TLS_Blockout.M_TLS_Blockout"));
        if (BaseMaterial)
        {
                UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(BaseMaterial, this);
                if (MID)
                {
                        MID->SetVectorParameterValue(TEXT("Color"), FLinearColor::FromSRGBColor(Color));
                        BodyVisual->SetMaterial(0, MID);
                }
        }
        else
        {
                UE_LOG(LogTemp, Warning, TEXT("[TLS] M_TLS_Blockout material not found (run 02_import_and_calibrate.bat) - NPC %s stays grey."),
                        *DisplayName);
        }
}

void ATLSNPC::SetNameLabelText(const FString& Text)
{
        if (NameLabel)
        {
                NameLabel->SetText(FText::FromString(Text));
        }
}
