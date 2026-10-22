using System.Text.Json;

namespace Codex.OpenScavTransits;

public sealed class OpenScavTransitsConfig
{
    public List<string> ScavAccessMaps { get; set; } =
    [
        "tarkovstreets",
        "sandbox",
        "sandbox_high",
        "laboratory"
    ];

    public bool EnableExistingTransits { get; set; } = true;

    public bool IncludeDisabledSourceMaps { get; set; } = false;

    public bool AllowTransitToDisabledDestinationMaps { get; set; } = true;

    public List<string> ExcludedSourceMaps { get; set; } =
    [
        "base",
        "develop",
        "hideout",
        "privatearea",
        "suburbs",
        "terminal",
        "town"
    ];

    public List<string> ExcludedTransitNames { get; set; } =
    [
        "NY_FINAL"
    ];

    public List<string> ExcludedTransitDestinations { get; set; } =
    [
        "terminal"
    ];

    public TraderAvailabilityConfig TraderAvailability { get; set; } = new();

    internal static JsonSerializerOptions JsonOptions { get; } = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };
}

public sealed class TraderAvailabilityConfig
{
    public bool Enabled { get; set; } = true;

    public bool ReturnOnlyAvailableTraders { get; set; } = false;

    public string DefaultLocation { get; set; } = "sandbox";

    public string FenceTraderId { get; set; } = TraderIds.Fence;

    public int ExtraTraderCount { get; set; } = 2;

    public string RotationMode { get; set; } = "map";

    public List<string> RotationPool { get; set; } =
    [
        TraderIds.Prapor,
        TraderIds.Therapist,
        TraderIds.Skier,
        TraderIds.Peacekeeper,
        TraderIds.Mechanic,
        TraderIds.Ragman,
        TraderIds.Jaeger,
        TraderIds.Ref
    ];

    public Dictionary<string, List<string>> MapTraderRules { get; set; } = new(StringComparer.OrdinalIgnoreCase)
    {
        ["sandbox"] = [TraderIds.Therapist, TraderIds.Prapor],
        ["sandbox_high"] = [TraderIds.Therapist, TraderIds.Prapor],
        ["groundzero"] = [TraderIds.Therapist, TraderIds.Prapor],
        ["tarkovstreets"] = [TraderIds.Prapor, TraderIds.Skier],
        ["streets"] = [TraderIds.Prapor, TraderIds.Skier],
        ["bigmap"] = [TraderIds.Skier, TraderIds.Prapor],
        ["customs"] = [TraderIds.Skier, TraderIds.Prapor],
        ["woods"] = [TraderIds.Jaeger, TraderIds.Therapist],
        ["factory4_day"] = [TraderIds.Mechanic, TraderIds.Prapor],
        ["factory4_night"] = [TraderIds.Mechanic, TraderIds.Prapor],
        ["factoryday"] = [TraderIds.Mechanic, TraderIds.Prapor],
        ["factorynight"] = [TraderIds.Mechanic, TraderIds.Prapor],
        ["interchange"] = [TraderIds.Ragman, TraderIds.Mechanic],
        ["shoreline"] = [TraderIds.Peacekeeper, TraderIds.Therapist],
        ["lighthouse"] = [TraderIds.Peacekeeper, TraderIds.Jaeger],
        ["rezervbase"] = [TraderIds.Prapor, TraderIds.Mechanic],
        ["reserve"] = [TraderIds.Prapor, TraderIds.Mechanic],
        ["laboratory"] = [TraderIds.Mechanic, TraderIds.Peacekeeper],
        ["labs"] = [TraderIds.Mechanic, TraderIds.Peacekeeper],
        ["labyrinth"] = [TraderIds.Therapist, TraderIds.Peacekeeper]
    };
}

public static class TraderIds
{
    public const string Prapor = "54cb50c76803fa8b248b4571";
    public const string Therapist = "54cb57776803fa99248b456e";
    public const string Fence = "579dc571d53a0658a154fbec";
    public const string Skier = "58330581ace78e27b8b10cee";
    public const string Peacekeeper = "5935c25fb3acc3127c3d8cd9";
    public const string Mechanic = "5a7c2eca46aef81a7ca2145d";
    public const string Ragman = "5ac3b934156ae10c4430e83c";
    public const string Jaeger = "5c0647fdd443bc2504c2d371";
    public const string Ref = "6617beeaa9cfa777ca915b7c";
}
