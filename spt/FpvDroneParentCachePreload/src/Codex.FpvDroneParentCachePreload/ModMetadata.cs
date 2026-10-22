#nullable disable

using SemanticVersioning;
using SPTarkov.Server.Core.Models.Spt.Mod;
using SemRange = SemanticVersioning.Range;
using SemVersion = SemanticVersioning.Version;

namespace Codex.FpvDroneParentCachePreload;

public sealed record ModMetadata : AbstractModMetadata
{
    public override string ModGuid { get; init; } = "codex.fpvdronemod.parentcachepreload";
    public override string Name { get; init; } = "Codex FPV Drone Parent Cache Preload";
    public override string Author { get; init; } = "Codex";
    public override SemVersion Version { get; init; } = new("1.0.0", false);
    public override SemRange SptVersion { get; init; } = new("~4.0.0", false);
    public override string License { get; init; } = "MIT";
    public override bool? IsBundleMod { get; init; } = false;
    public override Dictionary<string, SemRange> ModDependencies { get; init; } = [];
    public override string Url { get; init; } = "";
    public override List<string> Contributors { get; init; } = [];
    public override List<string> Incompatibilities { get; init; } = [];
}
