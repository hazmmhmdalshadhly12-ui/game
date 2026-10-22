// THE LAST SIN: The Sin-Eater - M1
// TLSInteractable.cpp

#include "TLSInteractable.h"

#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"

ATLSInteractable::ATLSInteractable()
{
        PrimaryActorTick.bCanEverTick = false;

        RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

        BodyVisual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
        BodyVisual->SetupAttachment(RootComponent);
        BodyVisual->SetMobility(EComponentMobility::Movable);

        PromptLabel = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Prompt"));
        PromptLabel->SetupAttachment(RootComponent);
        PromptLabel->SetRelativeLocation(FVector(0.0f, 0.0f, 130.0f));
        PromptLabel->SetHorizontalAlignment(EHTA_Center);
        PromptLabel->SetTextRenderColor(FColor::FromHex("E8A34D"));
        PromptLabel->SetWorldSize(12.0f);
}

void ATLSInteractable::SetBlockoutColor(const FColor& Color)
{
        if (!BodyVisual) { return; }

        UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
        if (Cube)
        {
                BodyVisual->SetStaticMesh(Cube);
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
}

void ATLSInteractable::SetInteractScale(float ScaleXY, float ScaleZ)
{
        if (BodyVisual)
        {
                BodyVisual->SetRelativeScale3D(FVector(ScaleXY, ScaleXY, ScaleZ));
                BodyVisual->SetRelativeLocation(FVector(0.0f, 0.0f, ScaleZ * 50.0f));
        }
}

void ATLSInteractable::MarkConsumed()
{
        bConsumed = true;
        if (BodyVisual)
        {
                BodyVisual->SetVisibility(false);
        }
        if (PromptLabel)
        {
                PromptLabel->SetVisibility(false);
        }
}
