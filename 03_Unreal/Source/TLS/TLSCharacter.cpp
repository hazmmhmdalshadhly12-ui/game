// THE LAST SIN: The Sin-Eater - M0

#include "TLSCharacter.h"

#include "TLSVillageGameMode.h"

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

        // --- M1 interaction / UI actions ---
        InteractAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Interact"));
        InteractAction->ValueType = EInputActionValueType::Boolean;

        JournalAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Journal"));
        JournalAction->ValueType = EInputActionValueType::Boolean;

        CancelAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Cancel"));
        CancelAction->ValueType = EInputActionValueType::Boolean;

        RestoreAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Restore"));
        RestoreAction->ValueType = EInputActionValueType::Boolean;

        // --- M3.8 case-layer actions ---
        CaseFileAction = NewObject<UInputAction>(this, TEXT("IA_TLS_CaseFile"));
        CaseFileAction->ValueType = EInputActionValueType::Boolean;

        BoardAction = NewObject<UInputAction>(this, TEXT("IA_TLS_Board"));
        BoardAction->ValueType = EInputActionValueType::Boolean;

        const FKey DigitKeys[9] = {
                EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five,
                EKeys::Six, EKeys::Seven, EKeys::Eight, EKeys::Nine
        };
        for (int32 I = 0; I < 9; ++I)
        {
                UInputAction* DigitAction = NewObject<UInputAction>(this, *FString::Printf(TEXT("IA_TLS_Digit%d"), I + 1));
                DigitAction->ValueType = EInputActionValueType::Boolean;
                DigitActions.Add(DigitAction);
        }

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

        // M1: E interact, J journal, Esc cancel, R restore, 1-9 select.
        // M3.8: N case file, B deduction board.
        DefaultContext->MapKey(InteractAction, EKeys::E);
        DefaultContext->MapKey(JournalAction, EKeys::J);
        DefaultContext->MapKey(CancelAction, EKeys::Escape);
        DefaultContext->MapKey(RestoreAction, EKeys::R);
        DefaultContext->MapKey(CaseFileAction, EKeys::N);
        DefaultContext->MapKey(BoardAction, EKeys::B);
        for (int32 I = 0; I < 9; ++I)
        {
                DefaultContext->MapKey(DigitActions[I], DigitKeys[I]);
        }

        // --- Mapping context: gamepad ---
        // Sticks are signed axes: no negate modifiers needed.
        DefaultContext->MapKey(MoveForwardAction, EKeys::Gamepad_LeftY);
        DefaultContext->MapKey(MoveRightAction, EKeys::Gamepad_LeftX);
        DefaultContext->MapKey(TurnAction, EKeys::Gamepad_RightX);
        DefaultContext->MapKey(LookUpAction, EKeys::Gamepad_RightY);
        DefaultContext->MapKey(RunAction, EKeys::Gamepad_FaceButton_Bottom);
        DefaultContext->MapKey(CrouchAction, EKeys::Gamepad_LeftThumbstick);
        DefaultContext->MapKey(InteractAction, EKeys::Gamepad_FaceButton_Right);
        DefaultContext->MapKey(JournalAction, EKeys::Gamepad_FaceButton_Left);
        DefaultContext->MapKey(CancelAction, EKeys::Gamepad_Special_Right);
        // M3.8: Y opens the case file, right bumper the deduction board.
        DefaultContext->MapKey(CaseFileAction, EKeys::Gamepad_FaceButton_Top);
        DefaultContext->MapKey(BoardAction, EKeys::Gamepad_RightShoulder);

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

        EnhancedInput->BindAction(InteractAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_Interact);
        EnhancedInput->BindAction(JournalAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_Journal);
        EnhancedInput->BindAction(CancelAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_Cancel);
        EnhancedInput->BindAction(RestoreAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_Restore);
        EnhancedInput->BindAction(CaseFileAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_CaseFile);
        EnhancedInput->BindAction(BoardAction, ETriggerEvent::Started, this, &ATLSCharacter::Input_Board);

        void (ATLSCharacter::*DigitHandlers[9])(const FInputActionValue&) = {
                &ATLSCharacter::Input_Digit1, &ATLSCharacter::Input_Digit2, &ATLSCharacter::Input_Digit3,
                &ATLSCharacter::Input_Digit4, &ATLSCharacter::Input_Digit5, &ATLSCharacter::Input_Digit6,
                &ATLSCharacter::Input_Digit7, &ATLSCharacter::Input_Digit8, &ATLSCharacter::Input_Digit9
        };
        for (int32 I = 0; I < 9; ++I)
        {
                if (DigitActions.IsValidIndex(I) && DigitActions[I])
                {
                        EnhancedInput->BindAction(DigitActions[I], ETriggerEvent::Started, this, DigitHandlers[I]);
                }
        }

        bInputBound = true;
        UE_LOG(LogTemp, Log, TEXT("[TLS] TLSCharacter: input bound (move/look/run/crouch + interact/UI)."));
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


// ------------------------------------------------------------------ M1 interaction

ATLSVillageGameMode* ATLSCharacter::GetVillageGameMode() const
{
        UWorld* World = GetWorld();
        return World ? Cast<ATLSVillageGameMode>(World->GetAuthGameMode()) : nullptr;
}

void ATLSCharacter::Input_Interact(const FInputActionValue& Value)
{
        if (ATLSVillageGameMode* GM = GetVillageGameMode())
        {
                GM->OnInteractPressed();
        }
}

void ATLSCharacter::Input_CaseFile(const FInputActionValue& Value)
{
        if (ATLSVillageGameMode* GM = GetVillageGameMode())
        {
                GM->OnCaseFileToggle();
        }
}

void ATLSCharacter::Input_Board(const FInputActionValue& Value)
{
        if (ATLSVillageGameMode* GM = GetVillageGameMode())
        {
                GM->OnBoardToggle();
        }
}

void ATLSCharacter::Input_Journal(const FInputActionValue& Value)
{
        if (ATLSVillageGameMode* GM = GetVillageGameMode())
        {
                GM->OnJournalToggle();
        }
}

void ATLSCharacter::Input_Cancel(const FInputActionValue& Value)
{
        if (ATLSVillageGameMode* GM = GetVillageGameMode())
        {
                GM->OnCancelPressed();
        }
}

void ATLSCharacter::Input_Restore(const FInputActionValue& Value)
{
        if (ATLSVillageGameMode* GM = GetVillageGameMode())
        {
                GM->OnRestorePressed();
        }
}

void ATLSCharacter::Input_Digit1(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(1); } }
void ATLSCharacter::Input_Digit2(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(2); } }
void ATLSCharacter::Input_Digit3(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(3); } }
void ATLSCharacter::Input_Digit4(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(4); } }
void ATLSCharacter::Input_Digit5(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(5); } }
void ATLSCharacter::Input_Digit6(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(6); } }
void ATLSCharacter::Input_Digit7(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(7); } }
void ATLSCharacter::Input_Digit8(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(8); } }
void ATLSCharacter::Input_Digit9(const FInputActionValue& Value) { if (ATLSVillageGameMode* GM = GetVillageGameMode()) { GM->OnDigitPressed(9); } }
