using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using BepInEx.Logging;
using EFT;
using Newtonsoft.Json;
using UnityEngine;

namespace QuakeBrain.Telemetry
{
    internal sealed class TelemetryWriter
    {
        private const int DefaultMaxQueuedLines = 2000;
        private const int DefaultMaxLinesPerRaid = 50000;
        private const int DefaultFlushIntervalMs = 3000;

        private readonly string _outputDirectory;
        private readonly ManualLogSource _log;
        private readonly object _gate = new object();
        private readonly Queue<TelemetryEnvelope> _queue = new Queue<TelemetryEnvelope>();
        private readonly AutoResetEvent _signal = new AutoResetEvent(false);

        private Thread _worker;
        private string _currentRaidKey;
        private string _currentPath;
        private bool _raidActive;
        private bool _workerStopping;
        private int _maxQueuedLines = DefaultMaxQueuedLines;
        private int _maxLinesPerRaid = DefaultMaxLinesPerRaid;
        private int _flushIntervalMs = DefaultFlushIntervalMs;
        private int _acceptedLines;
        private int _writtenLines;
        private int _droppedLines;

        public TelemetryWriter(string outputDirectory, ManualLogSource log)
        {
            _outputDirectory = outputDirectory;
            _log = log;
        }

        public void UpdateOptions(int maxQueuedLines, int maxLinesPerRaid, float flushIntervalSeconds)
        {
            lock (_gate)
            {
                _maxQueuedLines = Math.Max(100, maxQueuedLines);
                _maxLinesPerRaid = Math.Max(1000, maxLinesPerRaid);
                _flushIntervalMs = Math.Max(250, (int)(Math.Max(0.25f, flushIntervalSeconds) * 1000f));
            }
        }

        public void EnsureRaid(GameWorld world)
        {
            if (world == null || world.MainPlayer == null)
            {
                return;
            }

            var raidKey = $"{world.LocationId}:{world.MainPlayer.ProfileId}:{TelemetryModels.RaidStartKey}";
            if (IsCurrentRaid(raidKey))
            {
                return;
            }

            EndRaid("new_raid_started");

            Directory.CreateDirectory(_outputDirectory);
            TelemetryModels.ResetRaidClock();
            raidKey = $"{world.LocationId}:{world.MainPlayer.ProfileId}:{TelemetryModels.RaidStartKey}";

            var safeMap = SanitizeFilePart(world.LocationId ?? "unknown-map");
            var safeProfile = SanitizeFilePart(world.MainPlayer.ProfileId ?? "unknown-profile");
            var fileName = $"raid-{DateTime.Now:yyyyMMdd-HHmmss}-{safeMap}-{safeProfile}.jsonl";
            var path = Path.Combine(_outputDirectory, fileName);

            StartWorker(path, raidKey);

            Write("raid_start", new
            {
                plugin = Plugin.PluginName,
                version = Plugin.PluginVersion,
                map = world.LocationId,
                main_player = TelemetryModels.FromPlayer(world.MainPlayer, true),
                file = path
            });

            _log.LogInfo($"QuakeBrain telemetry started: {path}");
        }

        public bool Write(string type, object payload)
        {
            return Write(type, payload, false);
        }

        public bool Write(string type, object payload, bool force)
        {
            var envelope = new TelemetryEnvelope
            {
                type = type,
                utc = DateTime.UtcNow.ToString("O"),
                realtime = Time.realtimeSinceStartup,
                payload = payload
            };

            lock (_gate)
            {
                if (!_raidActive || _workerStopping)
                {
                    return false;
                }

                if (!force && _acceptedLines >= _maxLinesPerRaid)
                {
                    _droppedLines++;
                    return false;
                }

                if (!force && _queue.Count >= _maxQueuedLines)
                {
                    _droppedLines++;
                    return false;
                }

                _queue.Enqueue(envelope);
                _acceptedLines++;
                _signal.Set();
                return true;
            }
        }

        public void EndRaid(string reason)
        {
            bool shouldStop;
            int accepted;
            int written;
            int dropped;

            lock (_gate)
            {
                shouldStop = _raidActive && !_workerStopping;
                accepted = _acceptedLines;
                written = _writtenLines;
                dropped = _droppedLines;
            }

            if (!shouldStop)
            {
                return;
            }

            Write("raid_end", new
            {
                reason,
                raid_seconds = TelemetryModels.RaidSeconds,
                accepted_lines = accepted,
                written_lines = written,
                dropped_lines = dropped
            }, true);

            lock (_gate)
            {
                _raidActive = false;
                _workerStopping = true;
                _signal.Set();
            }

            var worker = _worker;
            if (worker != null && !worker.Join(1500))
            {
                _log.LogWarning("QuakeBrain telemetry writer is still draining in the background.");
                return;
            }

            _log.LogInfo($"QuakeBrain telemetry stopped: {_currentPath} accepted={_acceptedLines} written={_writtenLines} dropped={_droppedLines}");
        }

        private bool IsCurrentRaid(string raidKey)
        {
            lock (_gate)
            {
                return _raidActive && _currentRaidKey == raidKey;
            }
        }

        private void StartWorker(string path, string raidKey)
        {
            lock (_gate)
            {
                _queue.Clear();
                _currentRaidKey = raidKey;
                _currentPath = path;
                _raidActive = true;
                _workerStopping = false;
                _acceptedLines = 0;
                _writtenLines = 0;
                _droppedLines = 0;
            }

            _worker = new Thread(() => WorkerLoop(path))
            {
                IsBackground = true,
                Name = "QuakeBrainTelemetryWriter"
            };
            _worker.Start();
        }

        private void WorkerLoop(string path)
        {
            try
            {
                using (var writer = new StreamWriter(path, append: false))
                {
                    writer.AutoFlush = false;

                    while (true)
                    {
                        _signal.WaitOne(GetFlushIntervalMs());
                        DrainQueue(writer);
                        writer.Flush();

                        lock (_gate)
                        {
                            if (_workerStopping && _queue.Count == 0)
                            {
                                _workerStopping = false;
                                _currentRaidKey = null;
                                return;
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                _log.LogWarning($"QuakeBrain telemetry writer failed: {ex.Message}");
            }
            finally
            {
                lock (_gate)
                {
                    _raidActive = false;
                    _workerStopping = false;
                    _worker = null;
                    _currentRaidKey = null;
                }
            }
        }

        private void DrainQueue(StreamWriter writer)
        {
            while (true)
            {
                TelemetryEnvelope envelope;
                lock (_gate)
                {
                    if (_queue.Count == 0)
                    {
                        return;
                    }

                    envelope = _queue.Dequeue();
                }

                writer.WriteLine(JsonConvert.SerializeObject(envelope, Formatting.None));

                lock (_gate)
                {
                    _writtenLines++;
                }
            }
        }

        private int GetFlushIntervalMs()
        {
            lock (_gate)
            {
                return _flushIntervalMs;
            }
        }

        private static string SanitizeFilePart(string value)
        {
            foreach (var invalid in Path.GetInvalidFileNameChars())
            {
                value = value.Replace(invalid, '_');
            }

            return string.IsNullOrWhiteSpace(value) ? "unknown" : value;
        }
    }

    internal sealed class TelemetryEnvelope
    {
        public string type;
        public string utc;
        public float realtime;
        public object payload;
    }
}
