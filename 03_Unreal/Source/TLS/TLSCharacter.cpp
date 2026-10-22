// THE LAST SIN: The Sin-Eater - M0

#include "TLSCharacter.h"

#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputCoreTypes.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "UObject/ConstructorHelpers.h"

ATLSCharacter::ATLSCharacter()
{
        PrimaryActorTick.bCanEverTick = false;

        // Edmund Vale blockout stand-in: 175 cm total height (TLS-ENV-002 contract).
        GetCapsuleComponent()->InitCapsuleSize(35.0f, 87.5f);

        // Temporary visual: engine basic cube scaled into a 175 cm silhouette.
        // The real skeletal mesh + TLS_Rig_Human arrive with M1 per the docs.
        BodyVisual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BodyVisual"));
        BodyVisual->SetupAttachment(GetCapsuleComponent());
        BodyVisual->SetRelativeLocation(FVector(0.0f, 0.0f, -10.0f));
        BodyVisual->SetRelativeScale3D(FVector(0.5f, 0.5f, 1.55f));
        static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
        if (CubeFinder.Succeeded())
        {
                BodyVisual->SetStaticMesh(CubeFinder.Object);
        }
        BodyVisual->SetCollisionEnabled(ECollisionEnabled::NoCollision); // capsule drives collision

        // Third-person follow camera.
        CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
        CameraBoom->SetupAttachment(GetCapsuleComponent());
        CameraBoom->TargetArmLength = 400.0f;
        CameraBoom->SetRelativeRotation(FRotator(-20.0f, 0.0f, 0.0f));
        CameraBoom->bUsePawnControlRotation = true;
        CameraBoom->bEnableCameraLag = true;
        CameraBoom->CameraLagSpeed = 12.0f;

        FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
        FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
        FollowCamera->bUsePawnControlRotation = false;

        // Orient the body towards movement (classic third-person feel).
        bUseControllerRotationYaw = false;
        bUseControllerRotationPitch = false;

        UCharacterMovementComponent* Movement = GetCharacterMovement();
        Movement->bOrientRotationToMovement = true;
        Movement->RotationRate = FRotator(0.0f, 540.0f, 0.0f);
        Movement->MaxWalkSpeed = 250.0f;
        Movement->MaxWalkSpeedCrouched = 175.0f;
        Movement->GetNavAgentPropertiesRef().bCanCrouch = true;   // M0: walk / run / crouch - no jump
        Movement->JumpZVelocity = 0.0f;                           // jump intentionally disabled
        Movement->AirControl = 0.0f;
}

void ATLSCharacter::BeginPlay()
{
        Super::BeginPlay();

        BuildInputAssets();
        TryAddMappingContext();
        BindInputActions(); // covers the case where the input component already exists
}

void ATLSCharacter::NotifyControllerChanged()
{
        Super::NotifyControllerChanged();
        TryAddMappingContext();
        BindInputActions();
}

void ATLSCharacter::BuildInputAssets()
{
        if (DefaultContext)
        {
                return; // already built
        }

        // --- Actions ---
        MoveForwardAction = NewObject<UInputAction>(this, TEXT("IA_TLS_MoveForward"));
        MoveForwardAction->ValueType = EInputActionValueType::Axis1D;

        MoveRightAction = NewObject<UInputAction>(this, TEXT("IA_TLS_MoveRight"));
        MoveRightAction->ValueType = EInputActionValueType::Axis1D;

        TurnAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Turn"));
        TurnAction->ValueType = EInputActionValueType::Axis1D;

        LookUpAction = NewObject<UInputAction>(this, TEXT("IA_TLS_LookUp"));
        LookUpAction->ValueType = EInputActionValueType::Axis1D;

        RunAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Run"));
        RunAction->ValueType = EInputActionValueType::Boolean;

        CrouchAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Crouch"));
        CrouchAction->ValueType = EInputActionValueType::Boolean;

        // --- Mapping context: keyboard + mouse ---
        DefaultContext = NewObject<UInputMappingContext>(this, TEXT("IMC_TLS_Default"));

        DefaultContext->MapKey(MoveForwardAction, EKeys::W);
        DefaultContext->MapKey(MoveForwardAction, EKeys::S).Modifiers.Add(NewObject<UInputModifierNegate>(this));
        DefaultContext->MapKey(MoveRightAction, EKeys::D);
        DefaultContext->MapKey(MoveRightAction, EKeys::A).Modifiers.Add(NewObject<UInputModifierNegate>(this));

        // Mouse look: Y axis inverted (UE mouse convention: up movement = negative delta).
        DefaultContext->MapKey(TurnAction, EKeys::MouseX);
        DefaultContext->MapKey(LookUpAction, EKeys::MouseY).Modifiers.Add(NewObject<UInputModifierNegate>(this));

        // Hold Shift to run, hold C to crouch.
        DefaultContext->MapKey(RunAction, EKeys::LeftShift);
        DefaultContext->MapKey(CrouchAction, EKeys::C);

        // --- Mapping context: gamepad ---
        // Sticks are signed axes: no negate modifiers needed.
        DefaultContext->MapKey(MoveForwardAction, EKeys::Gamepad_LeftY);
        DefaultContext->MapKey(MoveRightAction, EKeys::Gamepad_LeftX);
        DefaultContext->MapKey(TurnAction, EKeys::Gamepad_RightX);
        DefaultContext->MapKey(LookUpAction, EKeys::Gamepad_RightY);
        DefaultContext->MapKey(RunAction, EKeys::Gamepad_FaceButton_Bottom);
        DefaultContext->MapKey(CrouchAction, EKeys::Gamepad_LeftThumbstick);

        UE_LOG(LogTemp, Log, TEXT("[M0] TLSCharacter: Enhanced Input context built (KB+M and gamepad)."));
}

void ATLSCharacter::TryAddMappingContext()
{
        if (!DefaultContext)
        {
                return;
        }

        APlayerController* PC = Cast<APlayerController>(GetController());
        if (!PC)
        {
                return;
        }

        ULocalPlayer* LP = PC->GetLocalPlayer();
        if (!LP)
        {
                return;
        }

        if (UEnhancedInputLocalPlayerSubsystem* Subsystem = LP->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
        {
                Subsystem->RemoveMappingContext(DefaultContext); // idempotent re-add
                Subsystem->AddMappingContext(DefaultContext, 0);
        }
}

void ATLSCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
        Super::SetupPlayerInputComponent(PlayerInputComponent);
        BindInputActions();
}

void ATLSCharacter::BindInputActions()
{
        if (bInputBound || !InputComponent)
        {
                return;
        }

        UEnhancedInputComponent* EnhancedInput = Cast<UEnhancedInputComponent>(InputComponent);
        if (!EnhancedInput)
        {
                UE_LOG(LogTemp, Warning, TEXT("[M0] TLSCharacter: UEnhancedInputComponent not found - input disabled."));
                return;
        }

        if (!MoveForwardAction || !MoveRightAction || !TurnAction || !LookUpAction || !RunAction || !CrouchAction)
        {
                return; // actions not built yet; re-tried on controller change
        }

        EnhancedInput->BindAction(MoveForwardAction, ETriggerEvent::Triggered, this, &ATLSCharacter::Input_MoveForward);
        EnhancedInput->BindAction(MoveRightAction, ETriggerEvent::Triggered, this, &ATLSCharacter::Input_MoveRight);
        EnhancedInput->BindAction(TurnAction, ETriggerEvent::Triggered, this, &ATLSCharacter::Input_Turn);
        EnhancedInput->BindAction(LookUpAction, ETriggerEvent::Triggered, this, &ATLSCharacter::Input_LookUp);
        EnhancedInput->BindAction(RunAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_RunStart);
        EnhancedInput->BindAction(RunAction, ETriggerEvent::Completed, this, &ATLSCharacter::Input_RunEnd);
        EnhancedInput->BindAction(CrouchAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_CrouchStart);
        EnhancedInput->BindAction(CrouchAction, ETriggerEvent::Completed, this, &ATLSCharacter::Input_CrouchEnd);

        bInputBound = true;
        UE_LOG(LogTemp, Log, TEXT("[M0] TLSCharacter: input bound (move/look/run/crouch)."));
}

void ATLSCharacter::Input_MoveForward(const FInputActionValue& Value)
{
        const float Axis = Value.Get<float>();
        if (Controller && Axis != 0.0f)
        {
                const FRotator YawRotation(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
                AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X), Axis);
        }
}

void ATLSCharacter::Input_MoveRight(const FInputActionValue& Value)
{
        const float Axis = Value.Get<float>();
        if (Controller && Axis != 0.0f)
        {
                const FRotator YawRotation(0.0f, Controller->GetControlRotation().Yaw, 0.0f);
                AddMovementInput(FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y), Axis);
        }
}

void ATLSCharacter::Input_Turn(const FInputActionValue& Value)
{
        AddControllerYawInput(Value.Get<float>());
}

void ATLSCharacter::Input_LookUp(const FInputActionValue& Value)
{
        AddControllerPitchInput(Value.Get<float>());
}

void ATLSCharacter::Input_RunStart(const FInputActionValue& Value)
{
        if (GetCharacterMovement())
        {
                GetCharacterMovement()->MaxWalkSpeed = RunSpeed;
        }
}

void ATLSCharacter::Input_RunEnd(const FInputActionValue& Value)
{
        if (GetCharacterMovement())
        {
                GetCharacterMovement()->MaxWalkSpeed = WalkSpeed;
        }
}

void ATLSCharacter::Input_CrouchStart(const FInputActionValue& Value)
{
        if (CanCrouch())
        {
                Crouch(false);
        }
}

void ATLSCharacter::Input_CrouchEnd(const FInputActionValue& Value)
{
        UnCrouch(false);
}
