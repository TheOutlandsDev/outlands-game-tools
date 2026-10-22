using System.Collections.Generic;
using EFT;
using UnityEngine;

namespace QuakeBrain.Telemetry
{
    internal static class LineOfSightSampler
    {
        public static List<LineOfSightSample> Sample(Player mainPlayer, BotOwner[] bots, int maxChecks)
        {
            var samples = new List<LineOfSightSample>();
            if (mainPlayer == null || bots == null || maxChecks <= 0)
            {
                return samples;
            }

            var origin = mainPlayer.Position + Vector3.up * 1.55f;
            var checks = 0;

            foreach (var bot in bots)
            {
                if (bot == null || bot.IsDead)
                {
                    continue;
                }

                if (checks++ >= maxChecks)
                {
                    break;
                }

                var target = bot.Position + Vector3.up * 1.45f;
                var direction = target - origin;
                var distance = direction.magnitude;
                var visible = false;

                if (distance > 0.1f)
                {
                    visible = !Physics.Raycast(origin, direction.normalized, distance, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore);
                }

                samples.Add(new LineOfSightSample
                {
                    bot_profile_id = bot.ProfileId,
                    distance = TelemetryModels.Round(distance),
                    main_can_see_bot = visible
                });
            }

            return samples;
        }
    }

    internal sealed class LineOfSightSample
    {
        public string bot_profile_id;
        public float distance;
        public bool main_can_see_bot;
    }
}

