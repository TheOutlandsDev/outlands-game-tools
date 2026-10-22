using EFT;
using HarmonyLib;

namespace QuakeBrain.Telemetry
{
    [HarmonyPatch(typeof(Player), "OnMakingShot")]
    internal static class PlayerShotPatch
    {
        private static void Postfix(Player __instance)
        {
            Plugin.RecordShot(__instance);
        }
    }

    [HarmonyPatch(typeof(Player), "ApplyDamageInfo")]
    internal static class PlayerDamagePatch
    {
        private static void Postfix(Player __instance, object[] __args)
        {
            Plugin.RecordDamage(__instance, __args);
        }
    }

    [HarmonyPatch(typeof(Player), "OnBeenKilledByAggressor")]
    internal static class PlayerDeathPatch
    {
        private static void Postfix(Player __instance, object[] __args)
        {
            Plugin.RecordDeath(__instance, __args);
        }
    }
}

