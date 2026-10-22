using EFT;

namespace QuakeBrain.Telemetry
{
    internal static class UtilityBrain
    {
        public static UtilityScores Score(BotOwner bot, float distanceToMain, bool haveEnemy, bool underFire, bool inCover)
        {
            var lateRaid = TelemetryModels.RaidSeconds > 1800f;
            var closeToMain = distanceToMain >= 0f && distanceToMain < 35f;
            var farFromMain = distanceToMain > 90f;
            var moving = bot != null && bot.HasPathAndNotComplete;

            var hold = Clamp((haveEnemy ? 0.55f : 0.15f) + (inCover ? 0.25f : 0f) + (underFire ? 0.1f : 0f));
            var rotate = Clamp((underFire ? 0.65f : 0.1f) + (haveEnemy && !inCover ? 0.2f : 0f) + (moving ? -0.1f : 0f));
            var flank = Clamp((haveEnemy ? 0.35f : 0.05f) + (!underFire && !inCover ? 0.15f : 0f));
            var retreat = Clamp((underFire && !inCover ? 0.65f : 0.08f) + (closeToMain ? 0.1f : 0f));
            var loot = Clamp((!haveEnemy && !underFire ? 0.45f : 0.02f) + (farFromMain ? 0.1f : 0f));
            var extract = Clamp((lateRaid ? 0.35f : 0.05f) + (!haveEnemy && farFromMain ? 0.15f : 0f));

            return new UtilityScores
            {
                hold = TelemetryModels.Round(hold),
                rotate = TelemetryModels.Round(rotate),
                flank = TelemetryModels.Round(flank),
                retreat = TelemetryModels.Round(retreat),
                loot = TelemetryModels.Round(loot),
                extract = TelemetryModels.Round(extract),
                best = Best(hold, rotate, flank, retreat, loot, extract)
            };
        }

        private static string Best(float hold, float rotate, float flank, float retreat, float loot, float extract)
        {
            var best = "hold";
            var score = hold;

            if (rotate > score) { best = "rotate"; score = rotate; }
            if (flank > score) { best = "flank"; score = flank; }
            if (retreat > score) { best = "retreat"; score = retreat; }
            if (loot > score) { best = "loot"; score = loot; }
            if (extract > score) { best = "extract"; }

            return best;
        }

        private static float Clamp(float value)
        {
            if (value < 0f) return 0f;
            if (value > 1f) return 1f;
            return value;
        }
    }

    internal sealed class UtilityScores
    {
        public float hold;
        public float rotate;
        public float flank;
        public float retreat;
        public float loot;
        public float extract;
        public string best;
    }
}

