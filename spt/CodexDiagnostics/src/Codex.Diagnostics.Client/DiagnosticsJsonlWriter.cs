using System;
using System.Collections.Concurrent;
using System.IO;
using System.Text;
using System.Threading;
using BepInEx.Logging;
using Newtonsoft.Json;
using UnityEngine;

namespace Codex.Diagnostics.Client
{
    internal sealed class DiagnosticsJsonlWriter : IDisposable
    {
        private readonly ManualLogSource _log;
        private readonly BlockingCollection<string> _queue;
        private readonly Thread _worker;
        private readonly StreamWriter _writer;
        private int _pendingFlushLines;
        private int _flushRequested;
        private int _droppedEvents;
        private bool _disposed;

        public DiagnosticsJsonlWriter(string outputDirectory, ManualLogSource log)
        {
            _log = log;
            Directory.CreateDirectory(outputDirectory);

            Path = System.IO.Path.Combine(outputDirectory, $"client-{DateTime.Now:yyyyMMdd-HHmmss}.jsonl");
            _queue = new BlockingCollection<string>(boundedCapacity: 4096);
            _writer = new StreamWriter(Path, append: false, encoding: new UTF8Encoding(encoderShouldEmitUTF8Identifier: false))
            {
                AutoFlush = false
            };
            _worker = new Thread(WriteLoop)
            {
                IsBackground = true,
                Name = "CodexDiagnosticsWriter"
            };
            _worker.Start();
        }

        public string Path { get; }

        public bool Write(string type, object payload)
        {
            if (_disposed)
            {
                return false;
            }

            var envelope = new
            {
                type = type,
                utc = DateTime.UtcNow.ToString("O"),
                realtime = Time.realtimeSinceStartup,
                payload = payload
            };

            try
            {
                var line = JsonConvert.SerializeObject(envelope, Formatting.None);
                if (_queue.TryAdd(line))
                {
                    return true;
                }
            }
            catch (InvalidOperationException)
            {
            }

            Interlocked.Increment(ref _droppedEvents);
            return false;
        }

        public int DrainDroppedEvents()
        {
            return Interlocked.Exchange(ref _droppedEvents, 0);
        }

        public void Flush()
        {
            Interlocked.Exchange(ref _flushRequested, 1);
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            _queue.CompleteAdding();
            if (!_worker.Join(5000))
            {
                _log.LogWarning("Diagnostics writer did not finish within 5 seconds.");
            }

            _writer.Dispose();
            _queue.Dispose();
        }

        private void WriteLoop()
        {
            try
            {
                while (!_queue.IsCompleted)
                {
                    string line;
                    if (_queue.TryTake(out line, 1000))
                    {
                        WriteLine(line);
                    }

                    if (_pendingFlushLines >= 50 || Interlocked.Exchange(ref _flushRequested, 0) == 1)
                    {
                        FlushInner();
                    }
                }

                FlushInner();
            }
            catch (Exception ex)
            {
                _log.LogWarning($"Diagnostics writer stopped: {ex.Message}");
            }
        }

        private void WriteLine(string line)
        {
            try
            {
                _writer.WriteLine(line);
                _pendingFlushLines++;
            }
            catch (Exception ex)
            {
                _log.LogWarning($"Diagnostics write failed: {ex.Message}");
            }
        }

        private void FlushInner()
        {
            if (_pendingFlushLines <= 0)
            {
                return;
            }

            try
            {
                _writer.Flush();
                _pendingFlushLines = 0;
            }
            catch (Exception ex)
            {
                _log.LogWarning($"Diagnostics flush failed: {ex.Message}");
            }
        }

    }
}
