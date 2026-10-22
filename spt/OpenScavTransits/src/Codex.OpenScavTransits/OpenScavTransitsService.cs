using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.Models.Eft.Common;
using SPTarkov.Server.Core.Services;
using SPTarkov.Server.Core.Utils.Logger;
using System.Reflection;
using System.Text.Json;

namespace Codex.OpenScavTransits;

[Injectable]
public sealed class OpenScavTransitsService(
    DatabaseService databaseService,
    SptLogger<OpenScavTransitsService> logger)
{
    private bool applied;

    public void Apply()
    {
        if (applied)
        {
            return;
        }

        applied = true;

        try
        {
            var config = LoadConfig();
            var locations = databaseService.GetLocations().GetDictionary();
            var normalizedMaps = BuildNormalizedLocationLookup(locations);
            var scavMaps = BuildNormalizedSet(config.ScavAccessMaps);
            var excludedSources = BuildNormalizedSet(config.ExcludedSourceMaps);
            var excludedTransitNames = BuildNormalizedSet(config.ExcludedTransitNames);
            var excludedDestinations = BuildNormalizedSet(config.ExcludedTransitDestinations);

            var scavChanged = 0;
            var scavAlreadyOpen = 0;
            var transitChanged = 0;
            var transitAlreadyActive = 0;
            var transitSkipped = 0;

            foreach (var (key, location) in locations)
            {
                var locationBase = location.Base;
                if (locationBase is null)
                {
                    continue;
                }

                if (IsConfiguredMap(key, locationBase, scavMaps))
                {
                    if (locationBase.DisabledForScav == false)
                    {
                        scavAlreadyOpen++;
                    }
                    else
                    {
                        locationBase.DisabledForScav = false;
                        scavChanged++;
                    }
                }

                if (!config.EnableExistingTransits)
                {
                    continue;
                }

                if (ShouldSkipSourceMap(key, locationBase, excludedSources, config.IncludeDisabledSourceMaps))
                {
                    continue;
                }

                foreach (var transit in locationBase.Transits ?? Enumerable.Empty<Transit>())
                {
                    if (!ShouldEnableTransit(
                            transit,
                            normalizedMaps,
                            excludedTransitNames,
                            excludedDestinations,
                            config.AllowTransitToDisabledDestinationMaps))
                    {
                        transitSkipped++;
                        continue;
                    }

                    if (transit.IsActive == true)
                    {
                        transitAlreadyActive++;
                        continue;
                    }

                    transit.IsActive = true;
                    transitChanged++;
                }
            }

            logger.Success(
                "Codex Open Scav Transits applied: " +
                $"{scavChanged} scav map flags opened, {scavAlreadyOpen} already open; " +
                $"{transitChanged} transits enabled, {transitAlreadyActive} already active, {transitSkipped} skipped by config.",
                null);
        }
        catch (Exception ex)
        {
            logger.Error("Codex Open Scav Transits failed while applying map/transit flags.", ex);
        }
    }

    private OpenScavTransitsConfig LoadConfig()
    {
        var configPath = GetConfigPath();
        var configDirectory = Path.GetDirectoryName(configPath);

        if (!string.IsNullOrWhiteSpace(configDirectory))
        {
            Directory.CreateDirectory(configDirectory);
        }

        if (!File.Exists(configPath))
        {
            var defaultConfig = new OpenScavTransitsConfig();
            File.WriteAllText(
                configPath,
                JsonSerializer.Serialize(defaultConfig, OpenScavTransitsConfig.JsonOptions));
            return defaultConfig;
        }

        try
        {
            var json = File.ReadAllText(configPath);
            return JsonSerializer.Deserialize<OpenScavTransitsConfig>(
                json,
                OpenScavTransitsConfig.JsonOptions) ?? new OpenScavTransitsConfig();
        }
        catch (Exception ex)
        {
            logger.Warning(
                $"Codex Open Scav Transits could not read config at {configPath}; using defaults.",
                ex);
            return new OpenScavTransitsConfig();
        }
    }

    private static string GetConfigPath()
    {
        var modDirectory = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)
            ?? AppContext.BaseDirectory;

        return Path.Combine(modDirectory, "config", "config.json");
    }

    private static Dictionary<string, Location> BuildNormalizedLocationLookup(
        Dictionary<string, Location> locations)
    {
        var lookup = new Dictionary<string, Location>(StringComparer.OrdinalIgnoreCase);

        foreach (var (key, location) in locations)
        {
            AddLocationAlias(lookup, key, location);

            if (location.Base is null)
            {
                continue;
            }

            AddLocationAlias(lookup, location.Base.Id, location);
            AddLocationAlias(lookup, location.Base.Name, location);
        }

        return lookup;
    }

    private static void AddLocationAlias(
        Dictionary<string, Location> lookup,
        string? alias,
        Location location)
    {
        var normalized = Normalize(alias);
        if (normalized.Length == 0)
        {
            return;
        }

        lookup.TryAdd(normalized, location);
    }

    private static HashSet<string> BuildNormalizedSet(IEnumerable<string> values)
    {
        return values
            .Select(Normalize)
            .Where(value => value.Length > 0)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static bool IsConfiguredMap(
        string key,
        LocationBase locationBase,
        HashSet<string> configuredMaps)
    {
        return configuredMaps.Contains(Normalize(key))
            || configuredMaps.Contains(Normalize(locationBase.Id))
            || configuredMaps.Contains(Normalize(locationBase.Name));
    }

    private static bool ShouldSkipSourceMap(
        string key,
        LocationBase locationBase,
        HashSet<string> excludedSources,
        bool includeDisabledSourceMaps)
    {
        if (!includeDisabledSourceMaps && !locationBase.Enabled)
        {
            return true;
        }

        return excludedSources.Contains(Normalize(key))
            || excludedSources.Contains(Normalize(locationBase.Id))
            || excludedSources.Contains(Normalize(locationBase.Name));
    }

    private static bool ShouldEnableTransit(
        Transit transit,
        Dictionary<string, Location> normalizedMaps,
        HashSet<string> excludedTransitNames,
        HashSet<string> excludedDestinations,
        bool allowTransitToDisabledDestinationMaps)
    {
        if (string.IsNullOrWhiteSpace(transit.Name) && string.IsNullOrWhiteSpace(transit.Location))
        {
            return false;
        }

        if (excludedTransitNames.Contains(Normalize(transit.Name)))
        {
            return false;
        }

        var destination = Normalize(transit.Location);
        if (excludedDestinations.Contains(destination))
        {
            return false;
        }

        if (!allowTransitToDisabledDestinationMaps
            && normalizedMaps.TryGetValue(destination, out var destinationLocation)
            && destinationLocation.Base?.Enabled == false)
        {
            return false;
        }

        return true;
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
}
