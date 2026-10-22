using System;
using System.Collections.Generic;
using System.IO;
using BepInEx;
using BepInEx.Configuration;
using EFT;
using HarmonyLib;
using UnityEngine;

namespace QuakeBrain.Telemetry
{
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "codex.quakebrain.telemetry";
        public const string PluginName = "QuakeBrain Telemetry";
        public const string PluginVersion = "0.3.0";

        private static Plugin _instance;

        private Harmony _harmony;
        private TelemetryWriter _writer;
        private ConfigEntry<bool> _enabled;
        private ConfigEntry<float> _sampleIntervalSeconds;
        private ConfigEntry<int> _maxLineOfSightChecksPerSample;
        private ConfigEntry<bool> _includeUtilityScores;
        private ConfigEntry<int> _maxBotsPerSnapshot;
        private ConfigEntry<int> _trackedBotCount;
        private ConfigEntry<float> _trackingStartDelaySeconds;
        private ConfigEntry<bool> _recordCombatEvents;
        private ConfigEntry<int> _maxCombatEventsPerSecond;
        private ConfigEntry<int> _maxQueuedLines;
        private ConfigEntry<int> _maxLinesPerRaid;
        private ConfigEntry<float> _flushIntervalSeconds;

        private readonly List<string> _trackedBotProfileIds = new List<string>();
        private GameWorld _currentWorld;
        private float _nextWorldScanAt;
        private float _nextSampleAt;
        private float _nextWriterOptionsAt;
        private float _trackingAllowedAt;
        private bool _wasInRaid;
        private int _eventBudgetSecond = -1;
        private int _eventBudgetUsed;

        public static bool HasInstance => _instance != null;

        private void Awake()
        {
            _instance = this;

            _enabled = Config.Bind("Capture", "Enabled", true, "Write passive QuakeBrain telemetry while in raid.");
            _sampleIntervalSeconds = Config.Bind("Capture", "Sample interval seconds", 5.0f, "Seconds between world snapshots.");
            _maxLineOfSightChecksPerSample = Config.Bind("Capture", "Max line-of-sight checks per sample", 5, "Caps raycast checks per snapshot to keep telemetry cheap.");
            _includeUtilityScores = Config.Bind("Capture", "Include utility scores", false, "Record hold/rotate/retreat/loot/extract scores without changing bot behavior.");
            _maxBotsPerSnapshot = Config.Bind("Capture", "Max bots per snapshot", 5, "Legacy cap for bot DTOs per snapshot. The tracked bot count is used first.");
            _trackedBotCount = Config.Bind("Tracking", "Tracked bot count", 5, "Number of AI lives to follow at a time.");
            _trackingStartDelaySeconds = Config.Bind("Tracking", "Tracking start delay seconds", 30.0f, "Seconds after raid start before picking AI to track.");
            _recordCombatEvents = Config.Bind("Capture", "Record combat events", true, "Record rate-limited shot/damage/death events.");
            _maxCombatEventsPerSecond = Config.Bind("Capture", "Max combat events per second", 10, "Caps shot/damage/death event lines per second.");
            _maxQueuedLines = Config.Bind("Writer", "Max queued lines", 2000, "Maximum telemetry lines buffered before low-priority lines are dropped.");
            _maxLinesPerRaid = Config.Bind("Writer", "Max lines per raid", 50000, "Maximum telemetry lines accepted per raid before low-priority lines are dropped.");
            _flushIntervalSeconds = Config.Bind("Writer", "Flush interval seconds", 3.0f, "Background writer flush interval.");

            _writer = new TelemetryWriter(Path.Combine(BepInEx.Paths.GameRootPath, "Logs", "QuakeBrainTelemetry"), Logger);
            ApplyWriterOptions();

            _harmony = new Harmony(PluginGuid);
            _harmony.PatchAll();

            Logger.LogInfo($"{PluginName} {PluginVersion} loaded. Passive capture only; bot behavior is not modified.");
        }

        private void OnDestroy()
        {
            try
            {
                _harmony?.UnpatchSelf();
                _writer?.EndRaid("plugin_destroyed");
            }
            catch (Exception ex)
            {
                Logger.LogWarning($"QuakeBrain shutdown warning: {ex}");
            }
        }

        private void Update()
        {
            if (!_enabled.Value)
            {
                if (_wasInRaid)
                {
                    _writer.EndRaid("capture_disabled");
                    _wasInRaid = false;
                }

                return;
            }

            var now = Time.realtimeSinceStartup;
            if (now >= _nextWriterOptionsAt)
            {
                _nextWriterOptionsAt = now + 5.0f;
                ApplyWriterOptions();
            }

            if (now >= _nextWorldScanAt)
            {
                _nextWorldScanAt = now + 2.0f;
                _currentWorld = UnityEngine.Object.FindObjectOfType<GameWorld>();
            }

            var inRaid = _currentWorld != null && _currentWorld.MainPlayer != null;
            if (!inRaid)
            {
                if (_wasInRaid)
                {
                    _writer.EndRaid("world_missing");
                    _wasInRaid = false;
                }

                return;
            }

            if (!_wasInRaid)
            {
                BeginRaidTracking(now);
            }

            _wasInRaid = true;
            _writer.EnsureRaid(_currentWorld);

            if (now >= _nextSampleAt)
            {
                _nextSampleAt = now + Mathf.Max(0.25f, _sampleIntervalSeconds.Value);
                RecordSnapshot(_currentWorld);
            }
        }

        public static void RecordShot(Player shooter)
        {
            if (!HasInstance || shooter == null)
            {
                return;
            }

            _instance.RecordShotInternal(shooter);
        }

        public static void RecordDamage(Player target, object[] args)
        {
            if (!HasInstance || target == null)
            {
                return;
            }

            _instance.RecordDamageInternal(target, args);
        }

        public static void RecordDeath(Player victim, object[] args)
        {
            if (!HasInstance || victim == null)
            {
                return;
            }

            _instance.RecordDeathInternal(victim, args);
        }

        private void RecordSnapshot(GameWorld world)
        {
            try
            {
                var players = new List<PlayerSample>();
                var alivePlayers = world.AllAlivePlayersList;
                if (alivePlayers != null)
                {
                    foreach (var player in alivePlayers)
                    {
                        if (player != null)
                        {
                            players.Add(TelemetryModels.FromPlayer(player, ReferenceEquals(player, world.MainPlayer)));
                        }
                    }
                }

                var bots = new List<BotSample>();
                var botOwners = UnityEngine.Object.FindObjectsOfType<BotOwner>();
                var trackedBots = UpdateTrackedBots(botOwners, world.MainPlayer, Time.realtimeSinceStartup);

                foreach (var bot in trackedBots)
                {
                    if (bot == null || bot.IsDead)
                    {
                        continue;
                    }
                    bots.Add(TelemetryModels.FromBot(bot, world.MainPlayer, _includeUtilityScores.Value));
                }

                var los = LineOfSightSampler.Sample(
                    world.MainPlayer,
                    trackedBots.ToArray(),
                    Mathf.Min(_maxLineOfSightChecksPerSample.Value, trackedBots.Count));

                _writer.Write("snapshot", new
                {
                    map = world.LocationId,
                    raid_seconds = TelemetryModels.RaidSeconds,
                    player_count = players.Count,
                    bot_count = bots.Count,
                    tracking = new
                    {
                        target_count = GetTargetBotCount(),
                        active_count = _trackedBotProfileIds.Count,
                        start_delay_remaining = Mathf.Max(0f, _trackingAllowedAt - Time.realtimeSinceStartup),
                        tracked_profile_ids = _trackedBotProfileIds.ToArray()
                    },
                    players,
                    bots,
                    line_of_sight = los
                });
            }
            catch (Exception ex)
            {
                Logger.LogWarning($"Snapshot failed: {ex.Message}");
            }
        }

        private void RecordShotInternal(Player shooter)
        {
            try
            {
                if (!CanRecordCombatEvent())
                {
                    return;
                }

                if (!IsTrackedOrMainPlayer(shooter))
                {
                    return;
                }

                _writer.EnsureRaid(_currentWorld);
                _writer.Write("shot", new
                {
                    shooter = TelemetryModels.FromPlayer(shooter, _currentWorld != null && ReferenceEquals(shooter, _currentWorld.MainPlayer)),
                    weapon = TelemetryModels.SafeItemName(TelemetryModels.SafeGet(shooter, "LastEquippedWeaponOrKnifeItem")),
                    raid_seconds = TelemetryModels.RaidSeconds
                });
            }
            catch (Exception ex)
            {
                Logger.LogWarning($"Shot telemetry failed: {ex.Message}");
            }
        }

        private void RecordDamageInternal(Player target, object[] args)
        {
            try
            {
                if (!CanRecordCombatEvent())
                {
                    return;
                }

                if (!IsTrackedOrMainPlayer(target))
                {
                    return;
                }

                _writer.EnsureRaid(_currentWorld);

                var damageInfo = args != null && args.Length > 0 ? args[0] : null;
                _writer.Write("damage", new
                {
                    target = TelemetryModels.FromPlayer(target, _currentWorld != null && ReferenceEquals(target, _currentWorld.MainPlayer)),
                    body_part = args != null && args.Length > 1 ? TelemetryModels.SafeString(args[1]) : null,
                    damage = TelemetryModels.SafeFloat(damageInfo, "Damage"),
                    damage_type = TelemetryModels.SafeString(TelemetryModels.SafeGet(damageInfo, "DamageType")),
                    source_id = TelemetryModels.SafeString(TelemetryModels.SafeGet(damageInfo, "SourceId")),
                    hit_point = TelemetryModels.SafeVector(TelemetryModels.SafeGet(damageInfo, "HitPoint")),
                    raid_seconds = TelemetryModels.RaidSeconds
                });
            }
            catch (Exception ex)
            {
                Logger.LogWarning($"Damage telemetry failed: {ex.Message}");
            }
        }

        private void RecordDeathInternal(Player victim, object[] args)
        {
            try
            {
                if (!CanRecordCombatEvent())
                {
                    return;
                }

                if (!IsTrackedOrMainPlayer(victim))
                {
                    return;
                }

                _writer.EnsureRaid(_currentWorld);

                var aggressor = args != null && args.Length > 0 ? args[0] : null;
                var damageInfo = args != null && args.Length > 1 ? args[1] : null;

                _writer.Write("death", new
                {
                    victim = TelemetryModels.FromPlayer(victim, _currentWorld != null && ReferenceEquals(victim, _currentWorld.MainPlayer)),
                    aggressor = TelemetryModels.FromIPlayer(aggressor),
                    body_part = args != null && args.Length > 2 ? TelemetryModels.SafeString(args[2]) : null,
                    damage_type = args != null && args.Length > 3 ? TelemetryModels.SafeString(args[3]) : TelemetryModels.SafeString(TelemetryModels.SafeGet(damageInfo, "DamageType")),
                    hit_point = TelemetryModels.SafeVector(TelemetryModels.SafeGet(damageInfo, "HitPoint")),
                    raid_seconds = TelemetryModels.RaidSeconds
                });
            }
            catch (Exception ex)
            {
                Logger.LogWarning($"Death telemetry failed: {ex.Message}");
            }
        }

        private void ApplyWriterOptions()
        {
            _writer.UpdateOptions(_maxQueuedLines.Value, _maxLinesPerRaid.Value, _flushIntervalSeconds.Value);
        }

        private bool CanRecordCombatEvent()
        {
            if (!_enabled.Value || !_recordCombatEvents.Value || _currentWorld == null || _currentWorld.MainPlayer == null)
            {
                return false;
            }

            var limit = Mathf.Max(0, _maxCombatEventsPerSecond.Value);
            if (limit == 0)
            {
                return false;
            }

            var second = Mathf.FloorToInt(Time.realtimeSinceStartup);
            if (second != _eventBudgetSecond)
            {
                _eventBudgetSecond = second;
                _eventBudgetUsed = 0;
            }

            if (_eventBudgetUsed >= limit)
            {
                return false;
            }

            _eventBudgetUsed++;
            return true;
        }

        private void BeginRaidTracking(float now)
        {
            _trackedBotProfileIds.Clear();
            _trackingAllowedAt = now + Mathf.Max(0f, _trackingStartDelaySeconds.Value);
            _eventBudgetSecond = -1;
            _eventBudgetUsed = 0;
        }

        private List<BotOwner> UpdateTrackedBots(BotOwner[] botOwners, Player mainPlayer, float now)
        {
            var result = new List<BotOwner>();
            var aliveByProfileId = new Dictionary<string, BotOwner>();

            if (botOwners == null)
            {
                _trackedBotProfileIds.Clear();
                return result;
            }

            foreach (var bot in botOwners)
            {
                if (bot == null || bot.IsDead || string.IsNullOrWhiteSpace(bot.ProfileId))
                {
                    continue;
                }

                if (!aliveByProfileId.ContainsKey(bot.ProfileId))
                {
                    aliveByProfileId.Add(bot.ProfileId, bot);
                }
            }

            for (var index = _trackedBotProfileIds.Count - 1; index >= 0; index--)
            {
                if (!aliveByProfileId.ContainsKey(_trackedBotProfileIds[index]))
                {
                    _trackedBotProfileIds.RemoveAt(index);
                }
            }

            var targetCount = GetTargetBotCount();
            if (now >= _trackingAllowedAt)
            {
                foreach (var pair in aliveByProfileId)
                {
                    if (_trackedBotProfileIds.Count >= targetCount)
                    {
                        break;
                    }

                    if (_trackedBotProfileIds.Contains(pair.Key))
                    {
                        continue;
                    }

                    _trackedBotProfileIds.Add(pair.Key);
                    _writer.Write("tracking_assigned", new
                    {
                        raid_seconds = TelemetryModels.RaidSeconds,
                        profile_id = pair.Key,
                        nickname = pair.Value.Profile != null ? pair.Value.Profile.Nickname : null,
                        position = TelemetryModels.FromVector(pair.Value.Position)
                    });
                }
            }

            foreach (var profileId in _trackedBotProfileIds)
            {
                BotOwner bot;
                if (aliveByProfileId.TryGetValue(profileId, out bot))
                {
                    result.Add(bot);
                }
            }

            return result;
        }

        private int GetTargetBotCount()
        {
            var tracked = Mathf.Max(0, _trackedBotCount.Value);
            if (tracked > 0)
            {
                return Mathf.Min(tracked, 20);
            }

            return Mathf.Min(Mathf.Max(0, _maxBotsPerSnapshot.Value), 20);
        }

        private bool IsTrackedOrMainPlayer(Player player)
        {
            if (player == null)
            {
                return false;
            }

            if (_currentWorld != null && ReferenceEquals(player, _currentWorld.MainPlayer))
            {
                return true;
            }

            return !string.IsNullOrWhiteSpace(player.ProfileId)
                && _trackedBotProfileIds.Contains(player.ProfileId);
        }
    }
}
