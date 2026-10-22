using SPTarkov.Server.Core.Models.Utils;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Codex.ScavLifeFramework;

public sealed class ScavLifeConfig
{
    public bool Enabled { get; set; } = true;
    public bool DevelopmentMode { get; set; } = false;
    public ScavLifeStartingScavConfig StartingScav { get; set; } = new();
    public ScavLifeStashConfig Stash { get; set; } = new();
    public ScavLifeCooldownConfig Cooldowns { get; set; } = new();
    public ScavLifeProgressionConfig Progression { get; set; } = new();
    public ScavLifeCustomizationConfig Customization { get; set; } = new();
    public ScavLifeDiagnosticsConfig Diagnostics { get; set; } = new();
}

public sealed class ScavLifeStartingScavConfig
{
    public string Nickname { get; set; } = "Local Runner";
    public int Level { get; set; } = 1;
    public int Experience { get; set; } = 0;
}

public sealed class ScavLifeStashConfig
{
    public int Width { get; set; } = 6;
    public int Height { get; set; } = 4;
    public bool CaptureSurvivedHauls { get; set; } = true;
    public bool AutoStoreSurvivedHauls { get; set; }
    public int MaxPendingHauls { get; set; } = 8;
    public int MaxStoredItemTrees { get; set; } = 120;
}

public sealed class ScavLifeCooldownConfig
{
    public int SurvivedMinutes { get; set; } = 0;
    public int DeathMinutes { get; set; } = 20;
}

public sealed class ScavLifeProgressionConfig
{
    public int SurvivedRunExperience { get; set; } = 120;
    public int DeathRunExperience { get; set; } = 15;
    public double LootValueToExperienceRatio { get; set; } = 0.01;
}

public sealed class ScavLifeCustomizationConfig
{
    public bool SyncToLivePlayerScav { get; set; }
    public bool ApplyLevelAndExperienceToLiveScav { get; set; }
}

public sealed class ScavLifeDiagnosticsConfig
{
    public bool WritePostRaidAudit { get; set; } = false;
    public int MaxPostRaidAuditFiles { get; set; } = 30;
}

public sealed class ScavLifeState
{
    public int SchemaVersion { get; set; } = 5;
    public Dictionary<string, ScavLifeProfileState> Profiles { get; set; } = [];
}

public sealed class ScavLifeProfileState
{
    public string ProfileId { get; set; } = "";
    public int Generation { get; set; } = 1;
    public long CreatedAtUnixTime { get; set; }
    public long LastUpdatedUnixTime { get; set; }
    public ScavLifeScav ActiveScav { get; set; } = new();
    public ScavLifeStash Stash { get; set; } = new();
    public List<ScavLifePendingHaul> PendingHauls { get; set; } = [];
    public ScavLifeStats Stats { get; set; } = new();
    public ScavLifeDossier Dossier { get; set; } = new();
}

public sealed class ScavLifeScav
{
    public string Id { get; set; } = "";
    public string Nickname { get; set; } = "";
    public bool Alive { get; set; } = true;
    public long ReadyAtUnixTime { get; set; }
    public int Level { get; set; } = 1;
    public int Experience { get; set; }
    public string LastLocation { get; set; } = "hideout";
    public ScavLifeCustomization Customization { get; set; } = new();
}

public sealed class ScavLifeCustomization
{
    public string DisplayName { get; set; } = "";
    public string Archetype { get; set; } = "local";
    public string HomeMap { get; set; } = "tarkovstreets";
    public string Temperament { get; set; } = "cautious";
    public string Voice { get; set; } = "quiet";
    public string OutfitPreset { get; set; } = "scrapper";
    public List<string> Tags { get; set; } = ["local", "persistent"];
    public ScavLifeKitPreferences KitPreferences { get; set; } = new();
}

public sealed class ScavLifeKitPreferences
{
    public string PrimaryWeapon { get; set; } = "whatever-runs";
    public string Armor { get; set; } = "light";
    public string Backpack { get; set; } = "small-pack";
    public string Medical { get; set; } = "balanced";
    public string LootFocus { get; set; } = "hardware";
}

public sealed class ScavLifeStash
{
    public int Width { get; set; }
    public int Height { get; set; }
    public List<ScavLifeStashItem> Items { get; set; } = [];
}

public sealed class ScavLifeStashItem
{
    public string Id { get; set; } = "";
    public string TemplateId { get; set; } = "";
    public int StackCount { get; set; } = 1;
    public string Source { get; set; } = "framework";
    public string Status { get; set; } = "stored";
    public string SourceHaulId { get; set; } = "";
    public string OriginalRootItemId { get; set; } = "";
    public string RootParentId { get; set; } = "";
    public string RootSlotId { get; set; } = "";
    public int ItemCount { get; set; } = 1;
    public long CapturedAtUnixTime { get; set; }
    public List<JsonElement> ItemTree { get; set; } = [];
}

public sealed class ScavLifePendingHaul
{
    public string Id { get; set; } = "";
    public string CaptureKey { get; set; } = "";
    public string Location { get; set; } = "unknown";
    public string Status { get; set; } = "pending";
    public long CapturedAtUnixTime { get; set; }
    public int ItemTreeCount { get; set; }
    public int FlatItemCount { get; set; }
    public List<ScavLifeStashItem> Items { get; set; } = [];
    public List<ScavLifeHaulDecision> Decisions { get; set; } = [];
}

public sealed class ScavLifeHaulDecision
{
    public string Destination { get; set; } = "";
    public List<string> ItemIds { get; set; } = [];
    public long DecidedAtUnixTime { get; set; }
}

public sealed class ScavLifeStats
{
    public int RunsStarted { get; set; }
    public int RunsSurvived { get; set; }
    public int RunsFailed { get; set; }
    public int ItemsExtracted { get; set; }
    public int Kills { get; set; }
    public int TotalLootValue { get; set; }
}

public sealed class ScavLifeDossier
{
    public int SurvivalStreak { get; set; }
    public int BestSurvivalStreak { get; set; }
    public int Trust { get; set; } = 10;
    public int Stress { get; set; }
    public int Fatigue { get; set; }
    public string LastOutcome { get; set; } = "none";
    public string LastRaidLocation { get; set; } = "hideout";
    public int LastRaidLootValue { get; set; }
    public int LastRaidItemsExtracted { get; set; }
    public int LastRaidKills { get; set; }
    public long LastRaidUnixTime { get; set; }
    public string LastCaptureSource { get; set; } = "none";
    public string LastCaptureKey { get; set; } = "";
}

public sealed class ScavLifeProfileRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }
}

public sealed class ScavLifeSeedRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }

    [JsonPropertyName("nickname")]
    public string? Nickname { get; set; }

    [JsonPropertyName("force")]
    public bool Force { get; set; }
}

public sealed class ScavLifeCompleteRunRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }

    [JsonPropertyName("survived")]
    public bool Survived { get; set; } = true;

    [JsonPropertyName("location")]
    public string? Location { get; set; }

    [JsonPropertyName("lootValue")]
    public int LootValue { get; set; }

    [JsonPropertyName("itemsExtracted")]
    public int ItemsExtracted { get; set; }

    [JsonPropertyName("kills")]
    public int Kills { get; set; }
}

public sealed class ScavLifeCustomizeRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }

    [JsonPropertyName("nickname")]
    public string? Nickname { get; set; }

    [JsonPropertyName("archetype")]
    public string? Archetype { get; set; }

    [JsonPropertyName("homeMap")]
    public string? HomeMap { get; set; }

    [JsonPropertyName("temperament")]
    public string? Temperament { get; set; }

    [JsonPropertyName("voice")]
    public string? Voice { get; set; }

    [JsonPropertyName("outfitPreset")]
    public string? OutfitPreset { get; set; }

    [JsonPropertyName("tags")]
    public List<string>? Tags { get; set; }

    [JsonPropertyName("kitPreferences")]
    public ScavLifeKitPreferencesRequest? KitPreferences { get; set; }
}

public sealed class ScavLifeKitPreferencesRequest
{
    [JsonPropertyName("primaryWeapon")]
    public string? PrimaryWeapon { get; set; }

    [JsonPropertyName("armor")]
    public string? Armor { get; set; }

    [JsonPropertyName("backpack")]
    public string? Backpack { get; set; }

    [JsonPropertyName("medical")]
    public string? Medical { get; set; }

    [JsonPropertyName("lootFocus")]
    public string? LootFocus { get; set; }
}

public sealed class ScavLifeRandomizeCustomizationRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }

    [JsonPropertyName("nickname")]
    public string? Nickname { get; set; }
}

public sealed class ScavLifeRaidPlanRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }

    [JsonPropertyName("location")]
    public string? Location { get; set; }
}

public sealed class ScavLifeResetRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }
}

public sealed class ScavLifeStashDecisionRequest : IRequestData
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; set; }

    [JsonPropertyName("pendingHaulId")]
    public string? PendingHaulId { get; set; }

    [JsonPropertyName("itemIds")]
    public List<string>? ItemIds { get; set; }

    [JsonPropertyName("destination")]
    public string? Destination { get; set; }
}

public sealed class ScavLifeStatusResponse
{
    public string Mod { get; set; } = "Scav Life Framework";
    public string Version { get; set; } = "0.5.1";
    public bool Enabled { get; set; }
    public bool DevelopmentMode { get; set; }
    public string ProfileId { get; set; } = "";
    public bool CanDeploy { get; set; }
    public long ServerUnixTime { get; set; }
    public ScavLifeProfileState Profile { get; set; } = new();
}

public sealed class ScavLifeDossierResponse
{
    public string Mod { get; set; } = "Scav Life Framework";
    public string Version { get; set; } = "0.5.1";
    public string ProfileId { get; set; } = "";
    public long ServerUnixTime { get; set; }
    public bool CanDeploy { get; set; }
    public string Condition { get; set; } = "ready";
    public string Summary { get; set; } = "";
    public ScavLifeDossier Dossier { get; set; } = new();
}

public sealed class ScavLifeRaidPlanResponse
{
    public string Mod { get; set; } = "Scav Life Framework";
    public string Version { get; set; } = "0.5.1";
    public string ProfileId { get; set; } = "";
    public long ServerUnixTime { get; set; }
    public bool CanDeploy { get; set; }
    public string SuggestedMap { get; set; } = "";
    public string RiskLevel { get; set; } = "medium";
    public string Role { get; set; } = "";
    public string ExtractionStyle { get; set; } = "";
    public List<string> Objectives { get; set; } = [];
    public List<string> Avoid { get; set; } = [];
    public ScavLifeLoadoutPlan LoadoutPlan { get; set; } = new();
    public ScavLifeDossier Dossier { get; set; } = new();
}

public sealed class ScavLifeLoadoutPlan
{
    public string PrimaryWeapon { get; set; } = "";
    public string Armor { get; set; } = "";
    public string Backpack { get; set; } = "";
    public string Medical { get; set; } = "";
    public string LootFocus { get; set; } = "";
    public string BudgetTier { get; set; } = "barebones";
}

public sealed class ScavLifeActionResponse
{
    public string Action { get; set; } = "";
    public string ProfileId { get; set; } = "";
    public bool Changed { get; set; }
    public string Message { get; set; } = "";
    public ScavLifeStatusResponse Status { get; set; } = new();
}

public sealed class ScavLifeCustomizationOptionsResponse
{
    public List<string> Archetypes { get; set; } = [];
    public List<string> HomeMaps { get; set; } = [];
    public List<string> Temperaments { get; set; } = [];
    public List<string> Voices { get; set; } = [];
    public List<string> OutfitPresets { get; set; } = [];
    public ScavLifeKitPreferenceOptions KitPreferences { get; set; } = new();
}

public sealed class ScavLifeStashStatusResponse
{
    public string Mod { get; set; } = "Scav Life Framework";
    public string Version { get; set; } = "0.5.1";
    public string ProfileId { get; set; } = "";
    public long ServerUnixTime { get; set; }
    public ScavLifeStashRuleSummary Rules { get; set; } = new();
    public ScavLifeStash Stash { get; set; } = new();
    public List<ScavLifePendingHaul> PendingHauls { get; set; } = [];
}

public sealed class ScavLifeStashDecisionResponse
{
    public string Action { get; set; } = "stash-decision";
    public string ProfileId { get; set; } = "";
    public bool Changed { get; set; }
    public string Message { get; set; } = "";
    public ScavLifeStashStatusResponse Status { get; set; } = new();
}

public sealed class ScavLifeStashRuleSummary
{
    public string Rule { get; set; } = "Only gear extracted by a survived player scav can enter the Scav Life stash.";
    public bool CaptureSurvivedHauls { get; set; }
    public bool AutoStoreSurvivedHauls { get; set; }
    public int MaxPendingHauls { get; set; }
    public int MaxStoredItemTrees { get; set; }
    public List<string> Destinations { get; set; } = ["scav-stash", "pmc-stash", "fence"];
}

public sealed class ScavLifeKitPreferenceOptions
{
    public List<string> PrimaryWeapons { get; set; } = [];
    public List<string> Armor { get; set; } = [];
    public List<string> Backpacks { get; set; } = [];
    public List<string> Medical { get; set; } = [];
    public List<string> LootFocus { get; set; } = [];
}
