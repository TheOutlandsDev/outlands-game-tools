using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common;
using SPTarkov.Server.Core.Models.Eft.Common.Tables;
using SPTarkov.Server.Core.Models.Eft.Match;
using SPTarkov.Server.Core.Servers;
using SPTarkov.Server.Core.Utils.Logger;
using System.Reflection;
using System.Text.Json;

namespace Codex.OpenScavTransits;

[Injectable]
public sealed class TraderAvailabilityService(
    SaveServer saveServer,
    SptLogger<TraderAvailabilityService> logger)
{
    private readonly object stateLock = new();
    private OpenScavTransitsConfig? config;
    private TraderAvailabilityState? state;
    private string? lastLoggedAvailability;
    private string? lastLoggedProfileAvailability;

    public void Initialize()
    {
        var activeConfig = LoadConfig();
        var activeState = LoadState(activeConfig);

        lock (stateLock)
        {
            config = activeConfig;
            state = activeState;
        }

        if (activeConfig.TraderAvailability.Enabled)
        {
            logger.Info(
                "Codex trader availability enabled: Fence plus " +
                $"{Math.Max(0, activeConfig.TraderAvailability.ExtraTraderCount)} map traders; " +
                $"current location '{activeState.CurrentLocation}'.",
                null);
        }
    }

    public List<TraderBase> FilterTraders(MongoId sessionId, List<TraderBase> traders)
    {
        if (traders.Count == 0)
        {
            return traders;
        }

        var activeConfig = LoadConfig();
        if (!activeConfig.TraderAvailability.Enabled)
        {
            return traders;
        }

        var activeState = GetState(activeConfig);
        var allowedIds = ResolveAvailableTraderIds(activeConfig, activeState, traders);
        if (allowedIds.Count == 0)
        {
            return traders;
        }

        ApplyProfileTraderAvailability(sessionId, activeState, traders, allowedIds);

        var availabilityKey = $"{Normalize(activeState.CurrentLocation)}:{string.Join(",", allowedIds)}";
        if (!string.Equals(availabilityKey, lastLoggedAvailability, StringComparison.Ordinal))
        {
            lastLoggedAvailability = availabilityKey;
            logger.Info(
                "Codex trader availability for " +
                $"'{activeState.CurrentLocation}': {string.Join(", ", DescribeTraders(traders, allowedIds))}",
                null);
        }

        return traders;
    }

    public void RecordStartLocalRaid(StartLocalRaidRequestData request)
    {
        if (request is null || string.IsNullOrWhiteSpace(request.Location))
        {
            return;
        }

        UpdateLocation(request.Location, "raid_start", incrementRaidCounter: true);
    }

    public void RecordEndLocalRaid(EndLocalRaidRequestData request)
    {
        if (request is null)
        {
            return;
        }

        var nextLocation = request.LocationTransit?.Location;
        if (string.IsNullOrWhiteSpace(nextLocation))
        {
            nextLocation = request.LocationTransit?.SptLastVisitedLocation;
        }

        if (string.IsNullOrWhiteSpace(nextLocation))
        {
            return;
        }

        UpdateLocation(nextLocation, "raid_end", incrementRaidCounter: false);
    }

    private void UpdateLocation(string location, string source, bool incrementRaidCounter)
    {
        var activeConfig = LoadConfig();
        if (!activeConfig.TraderAvailability.Enabled)
        {
            return;
        }

        TraderAvailabilityState activeState;
        lock (stateLock)
        {
            activeState = state ?? LoadState(activeConfig);
            activeState.CurrentLocation = location;
            activeState.UpdatedUtc = DateTime.UtcNow.ToString("O");
            activeState.LastUpdateSource = source;
            if (incrementRaidCounter)
            {
                activeState.RaidCounter++;
            }

            state = activeState;
            SaveState(activeState);
        }

        logger.Info($"Codex trader location set to '{location}' from {source}.", null);
    }

    private HashSet<string> ResolveAvailableTraderIds(
        OpenScavTransitsConfig activeConfig,
        TraderAvailabilityState activeState,
        List<TraderBase> traders)
    {
        var traderConfig = activeConfig.TraderAvailability;
        var knownTraderIds = traders
            .Select(GetTraderId)
            .Where(id => !string.IsNullOrWhiteSpace(id))
            .Select(id => id!)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var allowed = new List<string>();
        AddTraderId(allowed, traderConfig.FenceTraderId, knownTraderIds);

        var extraTraderIds = ResolveExtraTraderIds(traderConfig, activeState);
        foreach (var traderId in extraTraderIds)
        {
            AddTraderId(allowed, traderId, knownTraderIds);
            if (allowed.Count >= Math.Max(1, traderConfig.ExtraTraderCount + 1))
            {
                break;
            }
        }

        if (allowed.Count < Math.Max(1, traderConfig.ExtraTraderCount + 1))
        {
            foreach (var traderId in traderConfig.RotationPool)
            {
                AddTraderId(allowed, traderId, knownTraderIds);
                if (allowed.Count >= Math.Max(1, traderConfig.ExtraTraderCount + 1))
                {
                    break;
                }
            }
        }

        return allowed.ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private void ApplyProfileTraderAvailability(
        MongoId sessionId,
        TraderAvailabilityState activeState,
        List<TraderBase> traders,
        HashSet<string> allowedIds)
    {
        try
        {
            var profile = saveServer.GetProfile(sessionId);
            if (profile?.CharacterData is null)
            {
                return;
            }

            var traderLookup = traders
                .Select(trader => new
                {
                    Id = GetTraderId(trader),
                    Trader = trader
                })
                .Where(entry => !string.IsNullOrWhiteSpace(entry.Id))
                .ToDictionary(entry => entry.Id!, entry => entry.Trader, StringComparer.OrdinalIgnoreCase);

            var changed = 0;
            changed += ApplyProfileTraderAvailability(
                profile.CharacterData.PmcData,
                traderLookup,
                allowedIds);
            changed += ApplyProfileTraderAvailability(
                profile.CharacterData.ScavData,
                traderLookup,
                allowedIds);

            var profileKey = $"{sessionId}:{Normalize(activeState.CurrentLocation)}:{string.Join(",", allowedIds)}";
            if (changed > 0 || !string.Equals(profileKey, lastLoggedProfileAvailability, StringComparison.Ordinal))
            {
                lastLoggedProfileAvailability = profileKey;
                logger.Info(
                    "Codex trader profile availability applied for " +
                    $"'{activeState.CurrentLocation}': {string.Join(", ", DescribeTraders(traders, allowedIds))}; " +
                    $"{changed} profile flags updated.",
                    null);
            }
        }
        catch (Exception ex)
        {
            logger.Warning(
                "Codex trader availability could not apply route to profile trader flags.",
                ex);
        }
    }

    private static int ApplyProfileTraderAvailability(
        PmcData? profile,
        Dictionary<string, TraderBase> traderLookup,
        HashSet<string> allowedIds)
    {
        if (profile?.TradersInfo is null)
        {
            return 0;
        }

        var changed = 0;

        foreach (var traderId in allowedIds)
        {
            if (!MongoId.IsValidMongoId(traderId))
            {
                continue;
            }

            var traderKey = new MongoId(traderId);
            if (!profile.TradersInfo.TryGetValue(traderKey, out var traderInfo))
            {
                traderLookup.TryGetValue(traderId, out var trader);
                profile.TradersInfo[traderKey] = CreateTraderInfo(trader, enabled: true);
                changed++;
                continue;
            }

            if (traderInfo.Disabled != false)
            {
                traderInfo.Disabled = false;
                changed++;
            }

            if (traderInfo.Unlocked != true)
            {
                traderInfo.Unlocked = true;
                changed++;
            }
        }

        foreach (var (traderKey, traderInfo) in profile.TradersInfo)
        {
            var traderId = (string)traderKey;
            if (allowedIds.Contains(traderId))
            {
                continue;
            }

            if (traderInfo.Disabled == true)
            {
                continue;
            }

            traderInfo.Disabled = true;
            changed++;
        }

        return changed;
    }

    private static TraderInfo CreateTraderInfo(TraderBase? trader, bool enabled)
    {
        return new TraderInfo
        {
            LoyaltyLevel = 1,
            SalesSum = 0,
            Standing = 0,
            NextResupply = trader?.NextResupply ?? DateTimeOffset.UtcNow.ToUnixTimeSeconds() + 3600,
            Unlocked = enabled,
            Disabled = !enabled
        };
    }

    private static IEnumerable<string> ResolveExtraTraderIds(
        TraderAvailabilityConfig traderConfig,
        TraderAvailabilityState activeState)
    {
        if (IsRandomRotation(traderConfig.RotationMode))
        {
            return traderConfig.RotationPool
                .Where(id => !string.Equals(id, traderConfig.FenceTraderId, StringComparison.OrdinalIgnoreCase))
                .OrderBy(id => StableHash($"{Normalize(activeState.CurrentLocation)}:{activeState.RaidCounter}:{id}"))
                .ToArray();
        }

        var location = Normalize(activeState.CurrentLocation);
        foreach (var (map, traderIds) in traderConfig.MapTraderRules)
        {
            if (Normalize(map) == location)
            {
                return traderIds;
            }
        }

        var defaultLocation = Normalize(traderConfig.DefaultLocation);
        foreach (var (map, traderIds) in traderConfig.MapTraderRules)
        {
            if (Normalize(map) == defaultLocation)
            {
                return traderIds;
            }
        }

        return traderConfig.RotationPool;
    }

    private TraderAvailabilityState GetState(OpenScavTransitsConfig activeConfig)
    {
        lock (stateLock)
        {
            state ??= LoadState(activeConfig);
            return state;
        }
    }

    private OpenScavTransitsConfig LoadConfig()
    {
        if (config is not null)
        {
            return config;
        }

        var configPath = GetConfigPath();
        try
        {
            if (!File.Exists(configPath))
            {
                return new OpenScavTransitsConfig();
            }

            var json = File.ReadAllText(configPath);
            config = JsonSerializer.Deserialize<OpenScavTransitsConfig>(
                json,
                OpenScavTransitsConfig.JsonOptions) ?? new OpenScavTransitsConfig();
            return config;
        }
        catch (Exception ex)
        {
            logger.Warning(
                $"Codex trader availability could not read config at {configPath}; using defaults.",
                ex);
            config = new OpenScavTransitsConfig();
            return config;
        }
    }

    private TraderAvailabilityState LoadState(OpenScavTransitsConfig activeConfig)
    {
        var statePath = GetStatePath();
        try
        {
            if (File.Exists(statePath))
            {
                var json = File.ReadAllText(statePath);
                var loaded = JsonSerializer.Deserialize<TraderAvailabilityState>(
                    json,
                    OpenScavTransitsConfig.JsonOptions);
                if (loaded is not null && !string.IsNullOrWhiteSpace(loaded.CurrentLocation))
                {
                    return loaded;
                }
            }
        }
        catch (Exception ex)
        {
            logger.Warning(
                $"Codex trader availability could not read state at {statePath}; using default location.",
                ex);
        }

        return new TraderAvailabilityState
        {
            CurrentLocation = activeConfig.TraderAvailability.DefaultLocation,
            UpdatedUtc = DateTime.UtcNow.ToString("O"),
            LastUpdateSource = "default"
        };
    }

    private void SaveState(TraderAvailabilityState activeState)
    {
        var statePath = GetStatePath();
        try
        {
            var directory = System.IO.Path.GetDirectoryName(statePath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            File.WriteAllText(
                statePath,
                JsonSerializer.Serialize(activeState, OpenScavTransitsConfig.JsonOptions));
        }
        catch (Exception ex)
        {
            logger.Warning(
                $"Codex trader availability could not save state at {statePath}.",
                ex);
        }
    }

    private static void AddTraderId(
        List<string> allowed,
        string? traderId,
        HashSet<string> knownTraderIds)
    {
        if (string.IsNullOrWhiteSpace(traderId))
        {
            return;
        }

        if (!knownTraderIds.Contains(traderId))
        {
            return;
        }

        if (allowed.Contains(traderId, StringComparer.OrdinalIgnoreCase))
        {
            return;
        }

        allowed.Add(traderId);
    }

    private static IEnumerable<string> DescribeTraders(
        List<TraderBase> traders,
        HashSet<string> allowedIds)
    {
        return traders
            .Where(trader =>
            {
                var traderId = GetTraderId(trader);
                return traderId is not null && allowedIds.Contains(traderId);
            })
            .Select(trader => $"{trader.Nickname ?? trader.Name} ({GetTraderId(trader)})");
    }

    private static string? GetTraderId(TraderBase trader)
    {
        return trader.Id.ToString();
    }

    private static bool IsRandomRotation(string? rotationMode)
    {
        return string.Equals(rotationMode, "random", StringComparison.OrdinalIgnoreCase)
            || string.Equals(rotationMode, "raid", StringComparison.OrdinalIgnoreCase)
            || string.Equals(rotationMode, "perRaid", StringComparison.OrdinalIgnoreCase);
    }

    private static int StableHash(string value)
    {
        unchecked
        {
            var hash = 23;
            foreach (var c in value)
            {
                hash = (hash * 31) + c;
            }

            return hash;
        }
    }

    private static string Normalize(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        return new string(value
            .Where(char.IsLetterOrDigit)
            .Select(char.ToLowerInvariant)
            .ToArray());
    }

    private static string GetConfigPath()
    {
        var modDirectory = System.IO.Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)
            ?? AppContext.BaseDirectory;

        return System.IO.Path.Combine(modDirectory, "config", "config.json");
    }

    private static string GetStatePath()
    {
        var modDirectory = System.IO.Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)
            ?? AppContext.BaseDirectory;

        return System.IO.Path.Combine(modDirectory, "data", "trader_availability_state.json");
    }
}

public sealed class TraderAvailabilityState
{
    public string CurrentLocation { get; set; } = "sandbox";

    public int RaidCounter { get; set; }

    public string UpdatedUtc { get; set; } = DateTime.UtcNow.ToString("O");

    public string LastUpdateSource { get; set; } = "default";
}
