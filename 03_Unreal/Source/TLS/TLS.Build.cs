// THE LAST SIN: The Sin-Eater - M1
// Primary runtime module "TLS".
// M1: "UMG"/"Slate"/"SlateCore" added for the code-built widgets
// (dialogue box, ledger board, journal, HUD - no .uasset UI files required).

using UnrealBuildTool;

public class TLS : ModuleRules
{
	public TLS(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"UMG",
			"Slate",
			"SlateCore"
		});

		// Pure C++17 game-logic core (Source/TLS/Core/) - compiled by MSVC here
		// AND by g++ in tools/core_tests/run_core_tests.sh (418/418 checks).
		// No UE includes inside Core/ - keep it that way.
	}
}
