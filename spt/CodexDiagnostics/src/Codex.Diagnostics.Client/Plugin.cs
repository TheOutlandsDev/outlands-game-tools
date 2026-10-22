using System;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using BepInEx;
using BepInEx.Bootstrap;
using BepInEx.Configuration;
using EFT;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.SceneManagement;

namespace Codex.Diagnostics.Client
{
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "codex.diagnostics.client";
        public const string PluginName = "Codex Diagnostics Client";
        public const string PluginVersion = "0.2.1";

        private readonly ConcurrentQueue<DiagnosticEvent> _events = new ConcurrentQueue<DiagnosticEvent>();
        private readonly object _logRateLock = new object();
        private readonly List<float> _sampleFrameMs = new List<float>(512);

        private ConfigEntry<bool> _enabled;
        private ConfigEntry<bool> _captureUnityLogs;
        private ConfigEntry<bool> _captureInfoLogs;
        private ConfigEntry<bool> _captureStartupSnapshots;
        private ConfigEntry<bool> _captureSystemSamples;
        private ConfigEntry<bool> _captureRaidSamples;
        private ConfigEntry<float> _sampleIntervalSeconds;
        private ConfigEntry<float> _systemSampleIntervalSeconds;
        private ConfigEntry<float> _raidSampleIntervalSeconds;
        private ConfigEntry<float> _hitchThresholdMs;
        private ConfigEntry<float> _hitchCooldownSeconds;
        private ConfigEntry<int> _maxUnityLogEventsPerSecond;
        private ConfigEntry<int> _maxQueuedEvents;
        private ConfigEntry<string> _runLabel;

        private DiagnosticsJsonlWriter _writer;
        private Process _process;
        private TimeSpan _lastCpuTime;
        private object _lastRaidContext;
        private string _activeSceneName;
        private float _lastFrameAt;
        private float _sampleStartedAt;
        private float _nextSampleAt;
        private float _lastSystemSampleAt;
        private float _nextSystemSampleAt;
        private float _nextRaidSampleAt;
        private float _nextFlushAt;
        private float _nextAllowedHitchLogAt;
        private int _sampleFrames;
        private float _sampleFrameSeconds;
        private float _sampleMaxFrameSeconds;
        private int _sampleHitches;
        private int _sampleFrameLe16;
        private int _sampleFrameLe33;
        private int _sampleFrameLe50;
        private int _sampleFrameLe100;
        private int _sampleFrameGt100;
        private int _queuedEventCount;
        private int _droppedQueueEvents;
        private int _droppedUnityLogEvents;
        private long _unityLogRateSecond;
        private int _unityLogRateCount;
        private int _lastGc0;
        private int _lastGc1;
        private int _lastGc2;
        private bool _startupSnapshotsWritten;

        private void Awake()
        {
            _enabled = Config.Bind("Capture", "Enabled", true, "Write Codex diagnostics while the client is running.");
            _runLabel = Config.Bind("Capture", "Run label", string.Empty, "Optional label written into the session_start event.");
            _sampleIntervalSeconds = Config.Bind("Performance", "Sample interval seconds", 1.0f, "Seconds between FPS/memory summaries.");
            _hitchThresholdMs = Config.Bind("Performance", "Hitch threshold ms", 50.0f, "Frame time at or above this value is recorded as a hitch.");
            _hitchCooldownSeconds = Config.Bind("Performance", "Hitch log cooldown seconds", 0.25f, "Minimum time between individual hitch events.");
            _captureSystemSamples = Config.Bind("System", "Capture process system samples", true, "Capture process CPU, memory and thread snapshots.");
            _systemSampleIntervalSeconds = Config.Bind("System", "System sample interval seconds", 5.0f, "Seconds between process/system snapshots.");
            _captureRaidSamples = Config.Bind("Raid", "Capture raid context samples", true, "Capture lightweight in-raid player/bot counts.");
            _raidSampleIntervalSeconds = Config.Bind("Raid", "Raid sample interval seconds", 5.0f, "Seconds between in-raid context snapshots.");
            _captureUnityLogs = Config.Bind("Logs", "Capture Unity warnings and errors", true, "Capture Unity warnings, errors and exceptions into diagnostics.");
            _captureInfoLogs = Config.Bind("Logs", "Capture Unity info logs", false, "Capture normal Unity log lines. Leave off unless chasing a specific spam issue.");
            _maxUnityLogEventsPerSecond = Config.Bind("Logs", "Max Unity log events per second", 80, "Drops excess Unity log events instead of letting logging cause stutters.");
            _maxQueuedEvents = Config.Bind("Safety", "Max queued events", 2000, "Drops events if the writer cannot keep up.");
            _captureStartupSnapshots = Config.Bind("Startup", "Capture loaded plugin and mod snapshots", true, "Record loaded BepInEx plugins and SPT mod folders once per client start.");

            if (!_enabled.Value)
            {
                Logger.LogInfo($"{PluginName} is disabled by config.");
                return;
            }

            var outputDirectory = Path.Combine(BepInEx.Paths.GameRootPath, "Logs", "CodexDiagnostics");
            _writer = new DiagnosticsJsonlWriter(outputDirectory, Logger);
            _process = Process.GetCurrentProcess();
            _lastCpuTime = _process.TotalProcessorTime;
            _lastGc0 = GC.CollectionCount(0);
            _lastGc1 = GC.CollectionCount(1);
            _lastGc2 = GC.CollectionCount(2);
            _activeSceneName = SafeActiveSceneName();

            _lastFrameAt = Time.realtimeSinceStartup;
            _sampleStartedAt = _lastFrameAt;
            _lastSystemSampleAt = _lastFrameAt;
            _nextSampleAt = _lastFrameAt + Mathf.Max(0.25f, _sampleIntervalSeconds.Value);
            _nextSystemSampleAt = _lastFrameAt + Mathf.Max(1.0f, _systemSampleIntervalSeconds.Value);
            _nextRaidSampleAt = _lastFrameAt + Mathf.Max(1.0f, _raidSampleIntervalSeconds.Value);
            _nextFlushAt = _lastFrameAt + 5.0f;

            Application.logMessageReceivedThreaded += OnUnityLog;
            SceneManager.sceneLoaded += OnSceneLoaded;

            Enqueue("session_start", new
            {
                plugin = PluginName,
                version = PluginVersion,
                label = _runLabel.Value,
                game_root = BepInEx.Paths.GameRootPath,
                diagnostics_file = _writer.Path,
                unity = Application.unityVersion,
                platform = Application.platform.ToString(),
                hardware = HardwareSnapshot()
            });

            EnqueueConfigSnapshot();
            Logger.LogInfo($"{PluginName} {PluginVersion} writing {Path.GetFileName(_writer.Path)}");
        }

        private void Start()
        {
            WriteStartupSnapshotsOnce();
        }

        private void OnDestroy()
        {
            if (_writer == null)
            {
                return;
            }

            Application.logMessageReceivedThreaded -= OnUnityLog;
            SceneManager.sceneLoaded -= OnSceneLoaded;

            Enqueue("session_end", new
            {
                reason = "plugin_destroyed",
                scene = SafeActiveSceneName()
            });

            FlushEvents(limit: int.MaxValue);
            _writer.Dispose();
            _writer = null;
        }

        private void Update()
        {
            if (_writer == null)
            {
                return;
            }

            WriteStartupSnapshotsOnce();
            TrackFrame();
            TrackSystemAndRaid();
            FlushEvents(limit: 250);

            var now = Time.realtimeSinceStartup;
            if (now >= _nextFlushAt)
            {
                _nextFlushAt = now + 5.0f;
                _writer.Flush();
            }
        }

        private void TrackFrame()
        {
            var now = Time.realtimeSinceStartup;
            var delta = Mathf.Max(0f, now - _lastFrameAt);
            var frameMs = delta * 1000f;
            _lastFrameAt = now;

            _sampleFrames++;
            _sampleFrameSeconds += delta;
            _sampleFrameMs.Add(frameMs);
            if (delta > _sampleMaxFrameSeconds)
            {
                _sampleMaxFrameSeconds = delta;
            }

            BucketFrame(frameMs);
            if (frameMs >= _hitchThresholdMs.Value)
            {
                _sampleHitches++;
                if (now >= _nextAllowedHitchLogAt)
                {
                    _nextAllowedHitchLogAt = now + Mathf.Max(0.05f, _hitchCooldownSeconds.Value);
                    Enqueue("hitch", new
                    {
                        frame_ms = Round(frameMs),
                        threshold_ms = _hitchThresholdMs.Value,
                        scene = ActiveSceneName(),
                        memory = MemorySnapshot(),
                        process = ProcessSnapshot(now, mutateCpuBaseline: false),
                        raid = _lastRaidContext
                    });
                }
            }

            if (now < _nextSampleAt)
            {
                return;
            }

            var sampleDuration = Mathf.Max(0.001f, now - _sampleStartedAt);
            var droppedQueue = Interlocked.Exchange(ref _droppedQueueEvents, 0);
            var droppedUnityLogs = Interlocked.Exchange(ref _droppedUnityLogEvents, 0);
            var gc0 = GC.CollectionCount(0);
            var gc1 = GC.CollectionCount(1);
            var gc2 = GC.CollectionCount(2);
            var percentiles = FramePercentiles();

            Enqueue("performance_sample", new
            {
                scene = ActiveSceneName(),
                duration_seconds = Round(sampleDuration),
                fps = Round(_sampleFrames / sampleDuration),
                avg_frame_ms = Round((_sampleFrameSeconds / Math.Max(1, _sampleFrames)) * 1000f),
                max_frame_ms = Round(_sampleMaxFrameSeconds * 1000f),
                p50_frame_ms = percentiles.P50,
                p95_frame_ms = percentiles.P95,
                p99_frame_ms = percentiles.P99,
                frame_buckets = new
                {
                    le_16_7_ms = _sampleFrameLe16,
                    le_33_3_ms = _sampleFrameLe33,
                    le_50_ms = _sampleFrameLe50,
                    le_100_ms = _sampleFrameLe100,
                    gt_100_ms = _sampleFrameGt100
                },
                hitch_count = _sampleHitches,
                gc = new
                {
                    gen0_delta = gc0 - _lastGc0,
                    gen1_delta = gc1 - _lastGc1,
                    gen2_delta = gc2 - _lastGc2,
                    gen0_total = gc0,
                    gen1_total = gc1,
                    gen2_total = gc2
                },
                queued_events = _queuedEventCount,
                dropped_queue_events = droppedQueue,
                dropped_unity_log_events = droppedUnityLogs,
                memory = MemorySnapshot()
            });

            _lastGc0 = gc0;
            _lastGc1 = gc1;
            _lastGc2 = gc2;
            _sampleFrames = 0;
            _sampleFrameSeconds = 0f;
            _sampleMaxFrameSeconds = 0f;
            _sampleHitches = 0;
            _sampleFrameMs.Clear();
            _sampleFrameLe16 = 0;
            _sampleFrameLe33 = 0;
            _sampleFrameLe50 = 0;
            _sampleFrameLe100 = 0;
            _sampleFrameGt100 = 0;
            _sampleStartedAt = now;
            _nextSampleAt = now + Mathf.Max(0.25f, _sampleIntervalSeconds.Value);
        }

        private void TrackSystemAndRaid()
        {
            var now = Time.realtimeSinceStartup;
            if (_captureSystemSamples.Value && now >= _nextSystemSampleAt)
            {
                _nextSystemSampleAt = now + Mathf.Max(1.0f, _systemSampleIntervalSeconds.Value);
                Enqueue("system_sample", new
                {
                    scene = ActiveSceneName(),
                    process = ProcessSnapshot(now, mutateCpuBaseline: true),
                    memory = MemorySnapshot()
                });
            }

            if (_captureRaidSamples.Value && now >= _nextRaidSampleAt)
            {
                _nextRaidSampleAt = now + Mathf.Max(1.0f, _raidSampleIntervalSeconds.Value);
                _lastRaidContext = RaidContextSnapshot();
                Enqueue("raid_sample", _lastRaidContext);
            }
        }

        private void OnUnityLog(string condition, string stackTrace, LogType type)
        {
            if (_writer == null || !_captureUnityLogs.Value)
            {
                return;
            }

            if (type == LogType.Log && !_captureInfoLogs.Value)
            {
                return;
            }

            if (!TryConsumeUnityLogBudget())
            {
                Interlocked.Increment(ref _droppedUnityLogEvents);
                return;
            }

            var includeStack = type == LogType.Exception || type == LogType.Error || type == LogType.Assert;
            Enqueue("unity_log", new
            {
                level = type.ToString(),
                message = Truncate(condition, 1200),
                stack = includeStack ? Truncate(stackTrace, 4000) : null,
                scene = ActiveSceneName()
            });
        }

        private bool TryConsumeUnityLogBudget()
        {
            var currentSecond = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            lock (_logRateLock)
            {
                if (_unityLogRateSecond != currentSecond)
                {
                    _unityLogRateSecond = currentSecond;
                    _unityLogRateCount = 0;
                }

                if (_unityLogRateCount >= Math.Max(1, _maxUnityLogEventsPerSecond.Value))
                {
                    return false;
                }

                _unityLogRateCount++;
                return true;
            }
        }

        private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            _activeSceneName = scene.name;
            Enqueue("scene_loaded", new
            {
                name = scene.name,
                path = scene.path,
                mode = mode.ToString()
            });
        }

        private void EnqueueConfigSnapshot()
        {
            Enqueue("config", new
            {
                sample_interval_seconds = _sampleIntervalSeconds.Value,
                hitch_threshold_ms = _hitchThresholdMs.Value,
                hitch_cooldown_seconds = _hitchCooldownSeconds.Value,
                capture_system_samples = _captureSystemSamples.Value,
                system_sample_interval_seconds = _systemSampleIntervalSeconds.Value,
                capture_raid_samples = _captureRaidSamples.Value,
                raid_sample_interval_seconds = _raidSampleIntervalSeconds.Value,
                capture_unity_logs = _captureUnityLogs.Value,
                capture_info_logs = _captureInfoLogs.Value,
                max_unity_log_events_per_second = _maxUnityLogEventsPerSecond.Value,
                max_queued_events = _maxQueuedEvents.Value
            });
        }

        private void WriteStartupSnapshotsOnce()
        {
            if (_startupSnapshotsWritten || !_captureStartupSnapshots.Value)
            {
                return;
            }

            _startupSnapshotsWritten = true;

            try
            {
                Enqueue("bepinex_plugins", new
                {
                    plugins = Chainloader.PluginInfos
                        .OrderBy(pair => pair.Key, StringComparer.OrdinalIgnoreCase)
                        .Select(pair => new
                        {
                            guid = pair.Key,
                            name = pair.Value.Metadata?.Name,
                            version = pair.Value.Metadata?.Version?.ToString(),
                            location = pair.Value.Location
                        })
                        .ToArray()
                });
            }
            catch (Exception ex)
            {
                Enqueue("diagnostics_error", new { source = "bepinex_plugins", message = ex.Message });
            }

            EnqueueDirectorySnapshot("client_plugin_files", Path.Combine(BepInEx.Paths.GameRootPath, "BepInEx", "plugins"), "*.dll");
            EnqueueDirectorySnapshot("server_mod_folders", Path.Combine(BepInEx.Paths.GameRootPath, "SPT", "user", "mods"), null);
        }

        private void EnqueueDirectorySnapshot(string type, string directory, string searchPattern)
        {
            try
            {
                if (!Directory.Exists(directory))
                {
                    Enqueue(type, new { directory, exists = false });
                    return;
                }

                var entries = searchPattern == null
                    ? Directory.GetDirectories(directory).Select(path => new FileSystemInfoPayload(path)).ToArray()
                    : Directory.GetFiles(directory, searchPattern, SearchOption.AllDirectories).Select(path => new FileSystemInfoPayload(path)).ToArray();

                Enqueue(type, new
                {
                    directory,
                    exists = true,
                    entries
                });
            }
            catch (Exception ex)
            {
                Enqueue("diagnostics_error", new { source = type, message = ex.Message });
            }
        }

        private void Enqueue(string type, object payload)
        {
            if (_writer == null)
            {
                return;
            }

            if (_queuedEventCount >= Math.Max(10, _maxQueuedEvents.Value))
            {
                Interlocked.Increment(ref _droppedQueueEvents);
                return;
            }

            _events.Enqueue(new DiagnosticEvent(type, payload));
            Interlocked.Increment(ref _queuedEventCount);
        }

        private void FlushEvents(int limit)
        {
            var count = 0;
            while (count < limit && _events.TryDequeue(out var diagnosticEvent))
            {
                Interlocked.Decrement(ref _queuedEventCount);
                if (!_writer.Write(diagnosticEvent.Type, diagnosticEvent.Payload))
                {
                    Interlocked.Increment(ref _droppedQueueEvents);
                }

                count++;
            }
        }

        private static object MemorySnapshot()
        {
            try
            {
                return new
                {
                    managed_mb = Round(GC.GetTotalMemory(forceFullCollection: false) / 1048576f),
                    allocated_mb = Round(Profiler.GetTotalAllocatedMemoryLong() / 1048576f),
                    reserved_mb = Round(Profiler.GetTotalReservedMemoryLong() / 1048576f),
                    unused_reserved_mb = Round(Profiler.GetTotalUnusedReservedMemoryLong() / 1048576f),
                    gc_gen0 = GC.CollectionCount(0),
                    gc_gen1 = GC.CollectionCount(1),
                    gc_gen2 = GC.CollectionCount(2)
                };
            }
            catch
            {
                return new
                {
                    managed_mb = Round(GC.GetTotalMemory(forceFullCollection: false) / 1048576f),
                    gc_gen0 = GC.CollectionCount(0),
                    gc_gen1 = GC.CollectionCount(1),
                    gc_gen2 = GC.CollectionCount(2)
                };
            }
        }

        private object ProcessSnapshot(float now, bool mutateCpuBaseline)
        {
            if (_process == null)
            {
                return null;
            }

            try
            {
                _process.Refresh();
                var cpuTime = _process.TotalProcessorTime;
                var elapsed = Math.Max(0.001f, now - _lastSystemSampleAt);
                var cpuPercent = ((cpuTime - _lastCpuTime).TotalSeconds / elapsed / Math.Max(1, Environment.ProcessorCount)) * 100.0;

                if (mutateCpuBaseline)
                {
                    _lastCpuTime = cpuTime;
                    _lastSystemSampleAt = now;
                }

                return new
                {
                    cpu_percent = Round((float)Math.Max(0.0, cpuPercent)),
                    total_cpu_seconds = Round((float)cpuTime.TotalSeconds),
                    working_set_mb = Round(_process.WorkingSet64 / 1048576f),
                    private_mb = Round(_process.PrivateMemorySize64 / 1048576f),
                    virtual_mb = Round(_process.VirtualMemorySize64 / 1048576f),
                    thread_count = _process.Threads.Count,
                    handle_count = SafeHandleCount(_process)
                };
            }
            catch (Exception ex)
            {
                return new { error = ex.Message };
            }
        }

        private object RaidContextSnapshot()
        {
            try
            {
                var world = UnityEngine.Object.FindObjectOfType<GameWorld>();
                if (world == null)
                {
                    return new
                    {
                        in_raid = false,
                        scene = ActiveSceneName()
                    };
                }

                var alivePlayers = 0;
                var alivePlayersList = world.AllAlivePlayersList;
                if (alivePlayersList != null)
                {
                    foreach (var player in alivePlayersList)
                    {
                        if (player != null)
                        {
                            alivePlayers++;
                        }
                    }
                }

                var botOwners = UnityEngine.Object.FindObjectsOfType<BotOwner>();
                var aliveBots = 0;
                foreach (var bot in botOwners)
                {
                    if (bot != null && !bot.IsDead)
                    {
                        aliveBots++;
                    }
                }

                return new
                {
                    in_raid = true,
                    scene = ActiveSceneName(),
                    location = world.LocationId,
                    main_player_profile_id = world.MainPlayer != null ? world.MainPlayer.ProfileId : null,
                    alive_players = alivePlayers,
                    bot_owners = botOwners.Length,
                    alive_bot_owners = aliveBots
                };
            }
            catch (Exception ex)
            {
                return new
                {
                    in_raid = false,
                    scene = ActiveSceneName(),
                    error = ex.Message
                };
            }
        }

        private static object HardwareSnapshot()
        {
            try
            {
                return new
                {
                    operating_system = SystemInfo.operatingSystem,
                    processor = SystemInfo.processorType,
                    processor_count = SystemInfo.processorCount,
                    system_memory_mb = SystemInfo.systemMemorySize,
                    graphics_device = SystemInfo.graphicsDeviceName,
                    graphics_vendor = SystemInfo.graphicsDeviceVendor,
                    graphics_memory_mb = SystemInfo.graphicsMemorySize,
                    graphics_api = SystemInfo.graphicsDeviceType.ToString(),
                    graphics_shader_level = SystemInfo.graphicsShaderLevel,
                    screen_width = Screen.width,
                    screen_height = Screen.height,
                    fullscreen = Screen.fullScreen,
                    quality_level = QualitySettings.GetQualityLevel(),
                    quality_name = QualitySettings.names != null && QualitySettings.names.Length > QualitySettings.GetQualityLevel()
                        ? QualitySettings.names[QualitySettings.GetQualityLevel()]
                        : null,
                    v_sync_count = QualitySettings.vSyncCount,
                    target_frame_rate = Application.targetFrameRate
                };
            }
            catch (Exception ex)
            {
                return new { error = ex.Message };
            }
        }

        private static string SafeActiveSceneName()
        {
            try
            {
                return SceneManager.GetActiveScene().name;
            }
            catch
            {
                return null;
            }
        }

        private string ActiveSceneName()
        {
            return _activeSceneName ?? SafeActiveSceneName();
        }

        private static string Truncate(string value, int maxLength)
        {
            if (string.IsNullOrEmpty(value) || value.Length <= maxLength)
            {
                return value;
            }

            return value.Substring(0, maxLength) + "...";
        }

        private static float Round(float value)
        {
            return (float)Math.Round(value, 3);
        }

        private void BucketFrame(float frameMs)
        {
            if (frameMs <= 16.7f)
            {
                _sampleFrameLe16++;
            }
            else if (frameMs <= 33.3f)
            {
                _sampleFrameLe33++;
            }
            else if (frameMs <= 50f)
            {
                _sampleFrameLe50++;
            }
            else if (frameMs <= 100f)
            {
                _sampleFrameLe100++;
            }
            else
            {
                _sampleFrameGt100++;
            }
        }

        private FramePercentileSnapshot FramePercentiles()
        {
            if (_sampleFrameMs.Count == 0)
            {
                return new FramePercentileSnapshot(0f, 0f, 0f);
            }

            var values = _sampleFrameMs.ToArray();
            Array.Sort(values);
            return new FramePercentileSnapshot(
                Percentile(values, 0.50f),
                Percentile(values, 0.95f),
                Percentile(values, 0.99f));
        }

        private static float Percentile(float[] values, float percentile)
        {
            if (values == null || values.Length == 0)
            {
                return 0f;
            }

            var index = Mathf.Clamp(Mathf.CeilToInt(values.Length * percentile) - 1, 0, values.Length - 1);
            return Round(values[index]);
        }

        private static int SafeHandleCount(Process process)
        {
            try
            {
                return process.HandleCount;
            }
            catch
            {
                return -1;
            }
        }

        private struct FramePercentileSnapshot
        {
            public FramePercentileSnapshot(float p50, float p95, float p99)
            {
                P50 = p50;
                P95 = p95;
                P99 = p99;
            }

            public float P50 { get; }
            public float P95 { get; }
            public float P99 { get; }
        }

        private sealed class DiagnosticEvent
        {
            public DiagnosticEvent(string type, object payload)
            {
                Type = type;
                Payload = payload;
            }

            public string Type { get; }
            public object Payload { get; }
        }

        private sealed class FileSystemInfoPayload
        {
            public FileSystemInfoPayload(string path)
            {
                var info = new FileInfo(path);
                name = info.Name;
                full_name = info.FullName;
                length = info.Exists ? info.Length : 0;
                last_write_utc = info.Exists ? info.LastWriteTimeUtc.ToString("O") : null;
            }

            public string name;
            public string full_name;
            public long length;
            public string last_write_utc;
        }
    }
}
