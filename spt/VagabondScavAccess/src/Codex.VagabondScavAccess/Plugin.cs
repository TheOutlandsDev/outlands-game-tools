using System;
using System.Collections.Generic;
using BepInEx;
using BepInEx.Configuration;
using EFT;
using EFT.UI;
using EFT.UI.Matchmaker;
using HarmonyLib;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Codex.VagabondScavAccess
{
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    [BepInDependency("dev.oogabooga.spt-vagabond", BepInDependency.DependencyFlags.SoftDependency)]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "codex.vagabond.scavaccess";
        public const string PluginName = "Codex Vagabond Scav Access";
        public const string PluginVersion = "0.1.1";

        private static Plugin _instance;

        private Harmony _harmony;
        private ConfigEntry<bool> _enabled;

        internal static bool Enabled => _instance == null || _instance._enabled == null || _instance._enabled.Value;

        private void Awake()
        {
            _instance = this;
            _enabled = Config.Bind("Compatibility", "Enabled", true, "Restore Scav side selection when Vagabond hides it.");

            _harmony = new Harmony(PluginGuid);
            _harmony.PatchAll();

            Logger.LogInfo($"{PluginName} {PluginVersion} loaded.");
        }

        private void OnDestroy()
        {
            try
            {
                _harmony?.UnpatchSelf();
            }
            catch (Exception ex)
            {
                Logger.LogWarning($"Shutdown warning: {ex.Message}");
            }
        }
    }

    [HarmonyPatch(typeof(MatchMakerSideSelectionScreen), "Update")]
    internal static class MatchMakerSideSelectionScreenPatch
    {
        private const string VagabondDisabledText = "Disabled (Vagabond Mod)";
        private static readonly HashSet<int> RestoredScreens = new HashSet<int>();

        [HarmonyPostfix]
        [HarmonyAfter(new[] { "dev.oogabooga.spt-vagabond" })]
        [HarmonyPriority(Priority.Last)]
        private static void Postfix(
            MatchMakerSideSelectionScreen __instance,
            UIAnimatedToggleSpawner ____savagesButton,
            UIAnimatedToggleSpawner ____pmcButton,
            TMP_Text ____savageBlockMessage,
            CanvasGroup ____savageBlocker,
            PlayerModelView ____savageModelView,
            Button ____savagesBigButton,
            ESideType ___esideType_0)
        {
            if (!Plugin.Enabled)
            {
                return;
            }

            var screenId = __instance != null ? __instance.GetInstanceID() : 0;
            var looksVagabondBlocked = ____savageBlockMessage != null
                && string.Equals(____savageBlockMessage.text, VagabondDisabledText, StringComparison.Ordinal);

            if (looksVagabondBlocked && screenId != 0)
            {
                RestoredScreens.Add(screenId);
            }

            if (!looksVagabondBlocked && (screenId == 0 || !RestoredScreens.Contains(screenId)))
            {
                return;
            }

            if (____savagesButton != null)
            {
                ____savagesButton.GameObject.SetActive(true);
                ____savagesButton.SetActive(true);

                var spawnedToggle = ____savagesButton.SpawnedObject;
                if (spawnedToggle != null)
                {
                    spawnedToggle.interactable = true;
                }
            }

            if (____savageModelView != null)
            {
                ____savageModelView.GameObject.SetActive(true);
            }

            if (____savagesBigButton != null)
            {
                ____savagesBigButton.gameObject.SetActive(true);
                ____savagesBigButton.interactable = true;
            }

            if (____savageBlocker != null)
            {
                ____savageBlocker.alpha = 1f;
                ____savageBlocker.interactable = true;
            }

            if (____savageBlockMessage != null)
            {
                ____savageBlockMessage.gameObject.SetActive(false);
            }

            ApplySelectedSideVisual(___esideType_0, ____pmcButton, ____savagesButton);
        }

        private static void ApplySelectedSideVisual(
            ESideType selectedSide,
            UIAnimatedToggleSpawner pmcButton,
            UIAnimatedToggleSpawner scavButton)
        {
            switch (selectedSide)
            {
                case ESideType.Pmc:
                    ToggleSilently(pmcButton, true);
                    ToggleSilently(scavButton, false);
                    break;
                case ESideType.Savage:
                    ToggleSilently(pmcButton, false);
                    ToggleSilently(scavButton, true);
                    break;
            }
        }

        private static void ToggleSilently(UIAnimatedToggleSpawner spawner, bool selected)
        {
            if (spawner == null)
            {
                return;
            }

            try
            {
                var spawnedToggle = spawner.SpawnedObject;
                if (spawnedToggle != null)
                {
                    spawnedToggle.interactable = true;
                    spawnedToggle.ToggleSilent(selected);
                }
            }
            catch
            {
                spawner.Boolean_0 = selected;
            }
        }
    }
}
