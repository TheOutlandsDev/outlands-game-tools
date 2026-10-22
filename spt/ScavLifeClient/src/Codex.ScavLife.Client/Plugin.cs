using System;
using System.Collections.Concurrent;
using System.Linq;
using System.Threading.Tasks;
using BepInEx;
using BepInEx.Configuration;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using SPT.Common.Http;
using UnityEngine;

namespace Codex.ScavLife.Client
{
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "codex.scavlife.client";
        public const string PluginName = "Codex Scav Life Client";
        public const string PluginVersion = "0.1.0";

        private readonly ConcurrentQueue<Action> _mainThreadActions = new ConcurrentQueue<Action>();
        private ConfigEntry<bool> _enabled;
        private ConfigEntry<KeyboardShortcut> _toggleShortcut;
        private ConfigEntry<float> _autoRefreshSeconds;
        private Rect _window = new Rect(32f, 96f, 560f, 620f);
        private Vector2 _scroll;
        private JObject _stashStatus;
        private string _message = "Open after login, then refresh.";
        private bool _visible;
        private bool _busy;
        private float _nextRefreshAt;

        private void Awake()
        {
            _enabled = Config.Bind("General", "Enabled", true, "Show the in-game Scav Life panel.");
            _toggleShortcut = Config.Bind("General", "Toggle shortcut", new KeyboardShortcut(KeyCode.F8), "Toggle the Scav Life panel.");
            _autoRefreshSeconds = Config.Bind("General", "Auto refresh seconds", 10.0f, "How often the panel refreshes while open. Set 0 to disable.");

            Logger.LogInfo($"{PluginName} {PluginVersion} loaded. Toggle with {_toggleShortcut.Value}.");
        }

        private void Update()
        {
            while (_mainThreadActions.TryDequeue(out var action))
            {
                action();
            }

            if (!_enabled.Value)
            {
                return;
            }

            if (_toggleShortcut.Value.IsDown())
            {
                _visible = !_visible;
                if (_visible)
                {
                    RefreshStashStatus();
                }
            }

            if (!_visible || _autoRefreshSeconds.Value <= 0f || Time.realtimeSinceStartup < _nextRefreshAt)
            {
                return;
            }

            RefreshStashStatus();
        }

        private void OnGUI()
        {
            if (!_enabled.Value || !_visible)
            {
                return;
            }

            _window = GUILayout.Window(GetInstanceID(), _window, DrawWindow, "Scav Life");
        }

        private void DrawWindow(int windowId)
        {
            GUILayout.BeginVertical();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button(_busy ? "Working..." : "Refresh", GUILayout.Width(110f)) && !_busy)
            {
                RefreshStashStatus();
            }

            if (GUILayout.Button("Close", GUILayout.Width(80f)))
            {
                _visible = false;
            }

            GUILayout.FlexibleSpace();
            GUILayout.EndHorizontal();

            GUILayout.Label(_message);
            GUILayout.Space(6f);

            _scroll = GUILayout.BeginScrollView(_scroll);
            if (_stashStatus == null)
            {
                GUILayout.Label("No Scav Life stash data loaded yet.");
            }
            else
            {
                DrawStatus(_stashStatus);
            }

            GUILayout.EndScrollView();
            GUILayout.EndVertical();
            GUI.DragWindow(new Rect(0f, 0f, 10000f, 22f));
        }

        private void DrawStatus(JObject status)
        {
            var profileId = Text(status, "profileId", "ProfileId");
            var stash = Obj(status, "stash", "Stash");
            var pendingHauls = Arr(status, "pendingHauls", "PendingHauls");
            var stashItems = Arr(stash, "items", "Items");

            GUILayout.Label($"Profile: {profileId}");
            GUILayout.Label($"Scav stash item trees: {stashItems.Count}");
            GUILayout.Label($"Pending survived hauls: {pendingHauls.Count}");
            GUILayout.Space(8f);

            if (pendingHauls.Count == 0)
            {
                GUILayout.Label("No pending survived scav haul yet. Extract as a scav to create one.");
                DrawStoredItems(stashItems);
                return;
            }

            GUILayout.Label("Pending Hauls");
            foreach (var haulToken in pendingHauls.OfType<JObject>())
            {
                DrawPendingHaul(haulToken);
            }

            DrawStoredItems(stashItems);
        }

        private void DrawPendingHaul(JObject haul)
        {
            var id = Text(haul, "id", "Id");
            var location = Text(haul, "location", "Location");
            var status = Text(haul, "status", "Status");
            var itemTreeCount = Int(haul, "itemTreeCount", "ItemTreeCount");
            var flatItemCount = Int(haul, "flatItemCount", "FlatItemCount");
            var items = Arr(haul, "items", "Items");

            GUILayout.BeginVertical(GUI.skin.box);
            GUILayout.Label($"{location} | {status} | {itemTreeCount} gear roots | {flatItemCount} total item records");

            var preview = items.OfType<JObject>().Take(8).ToList();
            foreach (var item in preview)
            {
                GUILayout.Label($"- {Text(item, "rootSlotId", "RootSlotId")} | {Text(item, "templateId", "TemplateId")} | x{Int(item, "stackCount", "StackCount")}");
            }

            if (items.Count > preview.Count)
            {
                GUILayout.Label($"+ {items.Count - preview.Count} more");
            }

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Move All To Scav Stash") && !_busy)
            {
                DecideHaul(id, "scav-stash");
            }

            GUILayout.Label("Moves only if matching PMC profile items can be removed safely.");
            GUILayout.EndHorizontal();
            GUILayout.EndVertical();
        }

        private void DrawStoredItems(JArray stashItems)
        {
            GUILayout.Space(10f);
            GUILayout.Label("Stored Scav Gear");
            if (stashItems.Count == 0)
            {
                GUILayout.Label("Scav stash is empty.");
                return;
            }

            foreach (var item in stashItems.OfType<JObject>().Take(24))
            {
                GUILayout.Label($"- {Text(item, "rootSlotId", "RootSlotId")} | {Text(item, "templateId", "TemplateId")} | {Int(item, "itemCount", "ItemCount")} records");
            }

            if (stashItems.Count > 24)
            {
                GUILayout.Label($"+ {stashItems.Count - 24} more stored item trees");
            }
        }

        private void RefreshStashStatus()
        {
            if (_busy)
            {
                return;
            }

            _busy = true;
            _message = "Refreshing Scav Life stash...";
            _nextRefreshAt = Time.realtimeSinceStartup + Mathf.Max(1f, _autoRefreshSeconds.Value);

            Task.Run(() =>
            {
                try
                {
                    var response = RequestHandler.PostJson("/singleplayer/scavlife/stash/status", "{}");
                    var data = UnwrapData(response);
                    _mainThreadActions.Enqueue(() =>
                    {
                        _stashStatus = data;
                        _message = "Scav Life stash refreshed.";
                        _busy = false;
                    });
                }
                catch (Exception ex)
                {
                    _mainThreadActions.Enqueue(() =>
                    {
                        _message = $"Scav Life refresh failed: {ex.Message}";
                        _busy = false;
                    });
                }
            });
        }

        private void DecideHaul(string pendingHaulId, string destination)
        {
            if (_busy || string.IsNullOrWhiteSpace(pendingHaulId))
            {
                return;
            }

            _busy = true;
            _message = "Applying Scav Life haul decision...";

            Task.Run(() =>
            {
                try
                {
                    var body = JsonConvert.SerializeObject(new
                    {
                        pendingHaulId,
                        destination
                    });
                    var response = RequestHandler.PostJson("/singleplayer/scavlife/stash/decision", body);
                    var data = UnwrapData(response);
                    _mainThreadActions.Enqueue(() =>
                    {
                        _message = Text(data, "message", "Message");
                        _stashStatus = Obj(data, "status", "Status") ?? _stashStatus;
                        _busy = false;
                    });
                }
                catch (Exception ex)
                {
                    _mainThreadActions.Enqueue(() =>
                    {
                        _message = $"Scav Life decision failed: {ex.Message}";
                        _busy = false;
                    });
                }
            });
        }

        private static JObject UnwrapData(string json)
        {
            var token = JToken.Parse(string.IsNullOrWhiteSpace(json) ? "{}" : json);
            var data = token["data"] ?? token["Data"] ?? token;
            return data as JObject ?? new JObject();
        }

        private static JObject Obj(JToken token, params string[] names)
        {
            return Pick(token, names) as JObject;
        }

        private static JArray Arr(JToken token, params string[] names)
        {
            return Pick(token, names) as JArray ?? new JArray();
        }

        private static string Text(JToken token, params string[] names)
        {
            var value = Pick(token, names);
            return value == null || value.Type == JTokenType.Null ? "" : value.ToString();
        }

        private static int Int(JToken token, params string[] names)
        {
            var value = Pick(token, names);
            return value == null || value.Type == JTokenType.Null ? 0 : value.Value<int>();
        }

        private static JToken Pick(JToken token, params string[] names)
        {
            if (token == null)
            {
                return null;
            }

            foreach (var name in names)
            {
                var value = token[name];
                if (value != null)
                {
                    return value;
                }
            }

            return null;
        }
    }
}
