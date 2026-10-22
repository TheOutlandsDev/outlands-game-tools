using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.Models.Eft.Common;
using SPTarkov.Server.Core.Services;
using SPTarkov.Server.Core.Utils.Logger;
using System.Reflection;
using System.Text.Json;

namespace Codex.AiPopulationTuning;

[Injectable]
public sealed class AiPopulationTuningService(
    DatabaseService databaseService,
    SptLogger<AiPopulationTuningService> logger)
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
            if (!config.Enabled)
            {
                logger.Info("Codex AI Population Tuning is disabled by config.", null);
                return;
            }

            var excludedMaps = BuildNormalizedSet(config.ExcludedMaps);
            var locations = databaseService.GetLocations().GetDictionary();
            var totalMapChanges = 0;
            var totalWaveChanges = 0;
            var totalPmcChanges = 0;

            foreach (var (key, location) in locations)
            {
                var locationBase = location.Base;
                if (locationBase is null)
                {
                    continue;
                }

                if (IsExcludedMap(key, locationBase, excludedMaps))
                {
                    continue;
                }

                if (!TryGetMapConfig(config, key, locationBase, out var mapConfig) || !mapConfig.Enabled)
                {
                    continue;
                }

                var result = ApplyMapTuning(key, locationBase, mapConfig, config);
                totalMapChanges += result.MapFieldChanges;
                totalWaveChanges += result.NormalWaveChanges;
                totalPmcChanges += result.PmcWaveChanges;

                if (config.LogMapDetails && result.HasChanges)
                {
                    logger.Info(
                        "Codex AI tuning " +
                        $"{key}: map fields {result.MapFieldChanges}, normal waves {result.NormalWaveChanges}, " +
                        $"PMC waves {result.PmcWaveChanges}.",
                        null);
                }
            }

            logger.Success(
                "Codex AI Population Tuning applied: " +
                $"{totalMapChanges} map field changes, {totalWaveChanges} normal scav wave changes, " +
                $"{totalPmcChanges} PMC wave chance changes.",
                null);
        }
        catch (Exception ex)
        {
            logger.Error("Codex AI Population Tuning failed while applying spawn settings.", ex);
        }
    }

    private TuningResult ApplyMapTuning(
        string mapKey,
        LocationBase locationBase,
        MapPopulationTuning mapConfig,
        AiPopulationTuningConfig config)
    {
        var result = new TuningResult();

        if (mapConfig.BotMaxAdd > 0)
        {
            var target = locationBase.BotMax + mapConfig.BotMaxAdd;
            if (mapConfig.BotMaxCap.HasValue)
            {
                target = Math.Min(target, mapConfig.BotMaxCap.Value);
            }

            if (target > locationBase.BotMax)
            {
                locationBase.BotMax = target;
                result.MapFieldChanges++;
            }
        }

        if (mapConfig.BotStartMaxSeconds.HasValue
            && locationBase.BotStart > mapConfig.BotStartMaxSeconds.Value)
        {
            locationBase.BotStart = mapConfig.BotStartMaxSeconds.Value;
            result.MapFieldChanges++;
        }

        if (mapConfig.BotSpawnCountStepMax.HasValue
            && locationBase.BotSpawnCountStep.HasValue
            && locationBase.BotSpawnCountStep.Value > mapConfig.BotSpawnCountStepMax.Value)
        {
            locationBase.BotSpawnCountStep = mapConfig.BotSpawnCountStepMax.Value;
            result.MapFieldChanges++;
        }

        if (mapConfig.BotSpawnPeriodCheckMaxSeconds.HasValue
            && locationBase.BotSpawnPeriodCheck.HasValue
            && locationBase.BotSpawnPeriodCheck.Value > mapConfig.BotSpawnPeriodCheckMaxSeconds.Value)
        {
            locationBase.BotSpawnPeriodCheck = mapConfig.BotSpawnPeriodCheckMaxSeconds.Value;
            result.MapFieldChanges++;
        }

        if (mapConfig.MaxBotPerZoneMin.HasValue
            && locationBase.MaxBotPerZone.HasValue
            && locationBase.MaxBotPerZone.Value < mapConfig.MaxBotPerZoneMin.Value)
        {
            locationBase.MaxBotPerZone = mapConfig.MaxBotPerZoneMin.Value;
            result.MapFieldChanges++;
        }

        if (config.TuneNormalScavWaves)
        {
            result.NormalWaveChanges = TuneNormalScavWaves(locationBase, mapConfig);
        }

        if (config.TunePmcWaves)
        {
            result.PmcWaveChanges = TunePmcWaves(locationBase, mapConfig);
        }

        return result;
    }

    private static int TuneNormalScavWaves(LocationBase locationBase, MapPopulationTuning mapConfig)
    {
        if (mapConfig.AssaultWaveSlotAdd <= 0 && mapConfig.AssaultWaveMinimumSlotsMax <= 0)
        {
            return 0;
        }

        var changed = 0;
        foreach (var wave in locationBase.Waves ?? [])
        {
            if (!IsNormalScavAssaultWave(wave))
            {
                continue;
            }

            var currentMax = wave.SlotsMax ?? 0;
            if (currentMax <= 0 && !mapConfig.TouchZeroSlotWaves)
            {
                continue;
            }

            var targetMax = currentMax;
            if (mapConfig.AssaultWaveMinimumSlotsMax > 0)
            {
                targetMax = Math.Max(targetMax, mapConfig.AssaultWaveMinimumSlotsMax);
            }

            if (mapConfig.AssaultWaveSlotAdd > 0)
            {
                targetMax += mapConfig.AssaultWaveSlotAdd;
            }

            targetMax = Math.Min(targetMax, Math.Max(1, mapConfig.AssaultWaveSlotsMaxCap));
            if (targetMax <= currentMax)
            {
                continue;
            }

            wave.SlotsMax = targetMax;
            if (wave.SlotsMin.HasValue && wave.SlotsMin.Value > targetMax)
            {
                wave.SlotsMin = targetMax;
            }

            changed++;
        }

        return changed;
    }

    private static int TunePmcWaves(LocationBase locationBase, MapPopulationTuning mapConfig)
    {
        if (!mapConfig.PmcBossChanceFloor.HasValue && mapConfig.PmcBossChanceAdd <= 0)
        {
            return 0;
        }

        var changed = 0;
        foreach (var wave in locationBase.BossLocationSpawn ?? [])
        {
            if (!IsPmcWave(wave))
            {
                continue;
            }

            var currentChance = wave.BossChance ?? 0;
            var targetChance = currentChance;

            if (mapConfig.PmcBossChanceFloor.HasValue)
            {
                targetChance = Math.Max(targetChance, mapConfig.PmcBossChanceFloor.Value);
            }

            if (mapConfig.PmcBossChanceAdd > 0)
            {
                targetChance += mapConfig.PmcBossChanceAdd;
            }

            targetChance = Math.Min(targetChance, mapConfig.PmcBossChanceCap);
            if (targetChance <= currentChance)
            {
                continue;
            }

            wave.BossChance = targetChance;
            changed++;
        }

        return changed;
    }

    private AiPopulationTuningConfig LoadConfig()
    {
        var configPath = GetConfigPath();
        var configDirectory = Path.GetDirectoryName(configPath);

        if (!string.IsNullOrWhiteSpace(configDirectory))
        {
            Directory.CreateDirectory(configDirectory);
        }

        if (!File.Exists(configPath))
        {
            var defaultConfig = new AiPopulationTuningConfig();
            File.WriteAllText(
                configPath,
                JsonSerializer.Serialize(defaultConfig, AiPopulationTuningConfig.JsonOptions));
            return defaultConfig;
        }

        try
        {
            var json = File.ReadAllText(configPath);
            return JsonSerializer.Deserialize<AiPopulationTuningConfig>(
                json,
                AiPopulationTuningConfig.JsonOptions) ?? new AiPopulationTuningConfig();
        }
        catch (Exception ex)
        {
            logger.Warning(
                $"Codex AI Population Tuning could not read config at {configPath}; using defaults.",
                ex);
            return new AiPopulationTuningConfig();
        }
    }

    private static bool IsNormalScavAssaultWave(Wave wave)
    {
        var spawnType = wave.WildSpawnType?.ToString();
        if (!string.Equals(spawnType, "assault", StringComparison.OrdinalIgnoreCase)
            && !string.Equals(spawnType, "assaultGroup", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        return string.Equals(wave.BotSide, "Savage", StringComparison.OrdinalIgnoreCase)
            || string.IsNullOrWhiteSpace(wave.BotSide);
    }

    private static bool IsPmcWave(BossLocationSpawn wave)
    {
        return IsPmcRole(wave.BossName) || IsPmcRole(wave.BossEscortType);
    }

    private static bool IsPmcRole(string? role)
    {
        return string.Equals(role, "pmcBEAR", StringComparison.OrdinalIgnoreCase)
            || string.Equals(role, "pmcUSEC", StringComparison.OrdinalIgnoreCase)
            || string.Equals(role, "pmcBot", StringComparison.OrdinalIgnoreCase);
    }

    private static bool TryGetMapConfig(
        AiPopulationTuningConfig config,
        string key,
        LocationBase locationBase,
        out MapPopulationTuning mapConfig)
    {
        return config.Maps.TryGetValue(key, out mapConfig!)
            || config.Maps.TryGetValue(locationBase.Id ?? string.Empty, out mapConfig!)
            || config.Maps.TryGetValue(locationBase.Name ?? string.Empty, out mapConfig!)
            || config.Maps.TryGetValue(Normalize(key), out mapConfig!)
            || config.Maps.TryGetValue(Normalize(locationBase.Id), out mapConfig!)
            || config.Maps.TryGetValue(Normalize(locationBase.Name), out mapConfig!);
    }

    private static bool IsExcludedMap(
        string key,
        LocationBase locationBase,
        HashSet<string> excludedMaps)
    {
        return excludedMaps.Contains(Normalize(key))
            || excludedMaps.Contains(Normalize(locationBase.Id))
            || excludedMaps.Contains(Normalize(locationBase.Name));
    }

    private static HashSet<string> BuildNormalizedSet(IEnumerable<string> values)
    {
        return values
            .Select(Normalize)
            .Where(value => value.Length > 0)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static string GetConfigPath()
    {
        var modDirectory = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)
            ?? AppContext.BaseDirectory;

        return Path.Combine(modDirectory, "config", "config.json");
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

    private sealed class TuningResult
    {
        public int MapFieldChanges { get; set; }

        public int NormalWaveChanges { get; set; }

        public int PmcWaveChanges { get; set; }

        public bool HasChanges => MapFieldChanges > 0 || NormalWaveChanges > 0 || PmcWaveChanges > 0;
    }
}
