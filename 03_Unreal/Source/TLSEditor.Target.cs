// THE LAST SIN: The Sin-Eater - M0
// Editor target: build with 03_Unreal/Scripts/01_build_editor.bat

using UnrealBuildTool;
using System.Collections.Generic;

public class TLSEditorTarget : TargetRules
{
	public TLSEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;

		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;

		ExtraModuleNames.Add("TLS");
	}
}
