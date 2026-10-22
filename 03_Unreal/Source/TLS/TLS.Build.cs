// THE LAST SIN: The Sin-Eater - M0
// Primary runtime module "TLS".

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
			"EnhancedInput"
		});
	}
}
