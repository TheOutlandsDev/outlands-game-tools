using System.Text.Json;

namespace Codex.AiPopulationTuning;

public sealed class AiPopulationTuningConfig
{
    public bool Enabled { get; set; } = true;

    public bool TuneNormalScavWaves { get; set; } = true;

    public bool TunePmcWaves { get; set; } = true;

    public bool LogMapDetails { get; set; } = true;

    public List<string> ExcludedMaps { get; set; } =
    [
        "base",
        "develop",
        "hideout",
        "privatearea",
        "suburbs",
        "terminal",
        "town"
    ];

    public Dictionary<string, MapPopulationTuning> Maps { get; set; } =
        new(StringComparer.OrdinalIgnoreCase)
        {
            ["bigmap"] = new()
            {
                BotMaxAdd = 4,
                BotMaxCap = 24,
                BotStartMaxSeconds = 20,
                BotSpawnCountStepMax = 3,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 4,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 2,
                AssaultWaveSlotsMaxCap = 4,
                PmcBossChanceFloor = 80,
                PmcBossChanceAdd = 10
            },
            ["factory4_day"] = MapPopulationTuning.Factory(),
            ["factory4_night"] = MapPopulationTuning.Factory(),
            ["interchange"] = new()
            {
                BotMaxAdd = 2,
                BotMaxCap = 32,
                BotStartMaxSeconds = 20,
                BotSpawnCountStepMax = 3,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 3,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 2,
                AssaultWaveSlotsMaxCap = 4,
                PmcBossChanceFloor = 80,
                PmcBossChanceAdd = 10
            },
            ["lighthouse"] = new()
            {
                BotMaxAdd = 2,
                BotMaxCap = 31,
                BotStartMaxSeconds = 20,
                BotSpawnCountStepMax = 3,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 8,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 1,
                AssaultWaveSlotsMaxCap = 3,
                PmcBossChanceFloor = 80,
                PmcBossChanceAdd = 10
            },
            ["rezervbase"] = new()
            {
                BotMaxAdd = 3,
                BotMaxCap = 31,
                BotStartMaxSeconds = 20,
                BotSpawnCountStepMax = 3,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 4,
                AssaultWaveSlotAdd = 0,
                PmcBossChanceFloor = 80,
                PmcBossChanceAdd = 10
            },
            ["sandbox"] = new()
            {
                BotMaxAdd = 3,
                BotMaxCap = 23,
                BotStartMaxSeconds = 60,
                BotSpawnCountStepMax = 2,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 5,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 2,
                AssaultWaveSlotsMaxCap = 4,
                PmcBossChanceFloor = 75,
                PmcBossChanceAdd = 10
            },
            ["sandbox_high"] = new()
            {
                BotMaxAdd = 3,
                BotMaxCap = 23,
                BotStartMaxSeconds = 60,
                BotSpawnCountStepMax = 2,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 5,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 2,
                AssaultWaveSlotsMaxCap = 4,
                PmcBossChanceFloor = 75,
                PmcBossChanceAdd = 10
            },
            ["shoreline"] = new()
            {
                BotMaxAdd = 3,
                BotMaxCap = 34,
                BotStartMaxSeconds = 20,
                BotSpawnCountStepMax = 3,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 4,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 1,
                AssaultWaveSlotsMaxCap = 3,
                PmcBossChanceFloor = 80,
                PmcBossChanceAdd = 10
            },
            ["tarkovstreets"] = new()
            {
                BotMaxAdd = 0,
                BotMaxCap = 48,
                BotStartMaxSeconds = 60,
                BotSpawnCountStepMax = 3,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 5,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 2,
                AssaultWaveSlotsMaxCap = 3,
                PmcBossChanceFloor = 80,
                PmcBossChanceAdd = 10
            },
            ["woods"] = new()
            {
                BotMaxAdd = 4,
                BotMaxCap = 34,
                BotStartMaxSeconds = 10,
                BotSpawnCountStepMax = 3,
                BotSpawnPeriodCheckMaxSeconds = 12,
                MaxBotPerZoneMin = 4,
                AssaultWaveSlotAdd = 1,
                AssaultWaveMinimumSlotsMax = 1,
                AssaultWaveSlotsMaxCap = 3,
                PmcBossChanceFloor = 80,
                PmcBossChanceAdd = 10
            }
        };

    internal static JsonSerializerOptions JsonOptions { get; } = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };
}

public sealed class MapPopulationTuning
{
    public bool Enabled { get; set; } = true;

    public int BotMaxAdd { get; set; } = 0;

    public int? BotMaxCap { get; set; }

    public int? BotStartMaxSeconds { get; set; }

    public int? BotSpawnCountStepMax { get; set; }

    public int? BotSpawnPeriodCheckMaxSeconds { get; set; }

    public int? MaxBotPerZoneMin { get; set; }

    public int AssaultWaveSlotAdd { get; set; } = 0;

    public int AssaultWaveMinimumSlotsMax { get; set; } = 0;

    public int AssaultWaveSlotsMaxCap { get; set; } = 4;

    public bool TouchZeroSlotWaves { get; set; } = false;

    public double? PmcBossChanceFloor { get; set; }

    public double PmcBossChanceAdd { get; set; } = 0;

    public double PmcBossChanceCap { get; set; } = 100;

    public static MapPopulationTuning Factory() => new()
    {
        BotMaxAdd = 0,
        BotMaxCap = null,
        BotStartMaxSeconds = null,
        BotSpawnCountStepMax = null,
        BotSpawnPeriodCheckMaxSeconds = 12,
        MaxBotPerZoneMin = 4,
        AssaultWaveSlotAdd = 0,
        PmcBossChanceFloor = 85,
        PmcBossChanceAdd = 5
    };
}
