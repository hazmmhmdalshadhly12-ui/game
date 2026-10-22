// THE LAST SIN: The Sin-Eater - M1
// TLSCharacter: blockout stand-in for Edmund Vale (175 cm).
// Movement contract per MILESTONE_PLAN M0: walk / run / crouch - NO jump.
// M1 additions: interaction / UI input (E interact, J journal, Esc cancel,
// R restore page, 1-9 selection) forwarded to the village game mode.
// Enhanced Input (KB+M and gamepad), built entirely in code (no .uasset).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputActionValue.h"
#include "TLSCharacter.generated.h"

class UInputAction;
class UInputMappingContext;
class UCameraComponent;
class UStaticMeshComponent;
class USpringArmComponent;

UCLASS()
class TLS_API ATLSCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ATLSCharacter();

	virtual void SetupPlayerInputComponent(class UInputComponent* PlayerInputComponent) override;

protected:
	virtual void BeginPlay() override;
	virtual void NotifyControllerChanged() override;

	// --- camera / visual ---
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	USpringArmComponent* CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	UCameraComponent* FollowCamera;

	/** Temporary grey-box visual (engine cube). Real skeletal mesh arrives with M1. */
	UPROPERTY(VisibleAnywhere, Category = "Visual")
	UStaticMeshComponent* BodyVisual;

	// --- Enhanced Input (built at runtime) ---
	UPROPERTY(Transient)
	UInputMappingContext* DefaultContext;

	UPROPERTY(Transient)
	UInputAction* MoveForwardAction;

	UPROPERTY(Transient)
	UInputAction* MoveRightAction;

	UPROPERTY(Transient)
	UInputAction* TurnAction;

	UPROPERTY(Transient)
	UInputAction* LookUpAction;

	UPROPERTY(Transient)
	UInputAction* RunAction;

	UPROPERTY(Transient)
	UInputAction* CrouchAction;

	// --- movement tuning (M0 test values, cm/s) ---
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	float WalkSpeed = 250.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
	float RunSpeed = 600.0f;

private:
	/** Creates the input actions and mapping context (code-only project). */
	void BuildInputAssets();

	/** (Re)adds the default mapping context to the owning local player. */
	void TryAddMappingContext();

	/** Binds the actions to the input component exactly once. */
	void BindInputActions();

	bool bInputBound = false;

	void Input_MoveForward(const FInputActionValue& Value);
	void Input_MoveRight(const FInputActionValue& Value);
	void Input_Turn(const FInputActionValue& Value);
	void Input_LookUp(const FInputActionValue& Value);
	void Input_RunStart(const FInputActionValue& Value);
	void Input_RunEnd(const FInputActionValue& Value);
	void Input_CrouchStart(const FInputActionValue& Value);
	void Input_CrouchEnd(const FInputActionValue& Value);
};
