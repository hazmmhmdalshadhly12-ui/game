// THE LAST SIN: The Sin-Eater - M0
// Game target (packaged builds). Editor binaries use TLSEditor.Target.cs.

using UnrealBuildTool;
using System.Collections.Generic;

public class TLSTarget : TargetRules
{
	public TLSTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;

		// Locked engine version policy (TECHNICAL_PIPELINE 1): UE 5.4 LTS.
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.Add("TLS");
	}
}
