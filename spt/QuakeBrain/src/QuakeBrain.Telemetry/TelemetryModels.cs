using System;
using System.Collections.Generic;
using System.Reflection;
using EFT;
using UnityEngine;

namespace QuakeBrain.Telemetry
{
    internal static class TelemetryModels
    {
        private static float _raidStartedAt = -1f;
        private static readonly object MemberCacheGate = new object();
        private static readonly Dictionary<string, MemberInfo> MemberCache = new Dictionary<string, MemberInfo>();
        private static readonly HashSet<string> MissingMemberCache = new HashSet<string>();

        public static string RaidStartKey { get; private set; } = Guid.NewGuid().ToString("N");

        public static float RaidSeconds => _raidStartedAt < 0f ? 0f : Time.realtimeSinceStartup - _raidStartedAt;

        public static void ResetRaidClock()
        {
            _raidStartedAt = Time.realtimeSinceStartup;
            RaidStartKey = Guid.NewGuid().ToString("N");
        }

        public static PlayerSample FromPlayer(Player player, bool isMain)
        {
            if (player == null)
            {
                return null;
            }

            var profile = player.Profile;
            return new PlayerSample
            {
                id = player.PlayerId,
                profile_id = player.ProfileId,
                account_id = player.AccountId,
                nickname = profile?.Nickname,
                side = profile != null ? profile.Side.ToString() : null,
                type = player.GetType().FullName,
                is_main = isMain,
                group_id = player.GroupId,
                team_id = player.TeamId,
                position = FromVector(player.Position),
                velocity = FromVector(player.Velocity),
                look = FromVector(player.LookDirection),
                pose = player.Pose.ToString(),
                health_status = player.HealthStatus.ToString(),
                sprinting = player.IsSprintEnabled,
                prone = player.IsInPronePose
            };
        }

        public static object FromIPlayer(object player)
        {
            if (player == null)
            {
                return null;
            }

            return new
            {
                type = player.GetType().FullName,
                id = SafeString(SafeGet(player, "Id")),
                profile_id = SafeString(SafeGet(player, "ProfileId")),
                account_id = SafeString(SafeGet(player, "AccountId")),
                side = SafeString(SafeGet(player, "Side")),
                position = SafeVector(SafeGet(player, "Position"))
            };
        }

        public static BotSample FromBot(BotOwner bot, Player mainPlayer, bool includeUtility)
        {
            if (bot == null)
            {
                return null;
            }

            var player = bot.GetPlayer;
            var position = bot.Position;
            var distanceToMain = mainPlayer != null ? Vector3.Distance(position, mainPlayer.Position) : -1f;
            var haveEnemy = SafeBool(bot.Memory, "HaveEnemy");
            var underFire = SafeBool(bot.Memory, "IsUnderFire");
            var inCover = SafeBool(bot.Memory, "IsInCover");

            return new BotSample
            {
                id = bot.Id,
                profile_id = bot.ProfileId,
                account_id = bot.AccountId,
                nickname = bot.Profile?.Nickname,
                side = bot.Side.ToString(),
                role = SafeString(SafeGet(bot.Profile, "Side")),
                bot_state = bot.BotState.ToString(),
                group_id = bot.GroupId,
                team_id = bot.TeamId,
                zone = bot.SpawnBotZone != null ? bot.SpawnBotZone.name : null,
                position = FromVector(position),
                velocity = FromVector(bot.Velocity),
                look = FromVector(bot.LookDirection),
                destination = SafeVector(bot.Destination),
                has_path = bot.HasPathAndNotComplete,
                have_enemy = haveEnemy,
                under_fire = underFire,
                in_cover = inCover,
                distance_to_main = Round(distanceToMain),
                player = player != null ? FromPlayer(player, false) : null,
                utility = includeUtility ? UtilityBrain.Score(bot, distanceToMain, haveEnemy, underFire, inCover) : null
            };
        }

        public static Vec3 FromVector(Vector3 vector)
        {
            return new Vec3
            {
                x = Round(vector.x),
                y = Round(vector.y),
                z = Round(vector.z)
            };
        }

        public static Vec3 SafeVector(object value)
        {
            if (value == null)
            {
                return null;
            }

            if (value is Vector3 vector)
            {
                return FromVector(vector);
            }

            return null;
        }

        public static object SafeGet(object instance, string name)
        {
            if (instance == null || string.IsNullOrWhiteSpace(name))
            {
                return null;
            }

            try
            {
                var type = instance.GetType();
                var member = GetCachedMember(type, name);

                if (member is PropertyInfo prop)
                {
                    return prop.GetValue(instance, null);
                }

                if (member is FieldInfo field)
                {
                    return field.GetValue(instance);
                }

                return null;
            }
            catch
            {
                return null;
            }
        }

        public static string SafeString(object value)
        {
            return value?.ToString();
        }

        public static float SafeFloat(object instance, string name)
        {
            var value = SafeGet(instance, name);
            if (value == null)
            {
                return 0f;
            }

            try
            {
                return Round(Convert.ToSingle(value));
            }
            catch
            {
                return 0f;
            }
        }

        public static bool SafeBool(object instance, string name)
        {
            var value = SafeGet(instance, name);
            return value is bool b && b;
        }

        public static string SafeItemName(object item)
        {
            if (item == null)
            {
                return null;
            }

            return SafeString(SafeGet(item, "Name"))
                ?? SafeString(SafeGet(item, "ShortName"))
                ?? SafeString(SafeGet(item, "LocalizedName"))
                ?? item.GetType().Name;
        }

        public static float Round(float value)
        {
            return (float)Math.Round(value, 3);
        }

        private static MemberInfo GetCachedMember(Type type, string name)
        {
            var key = type.FullName + "|" + name;
            lock (MemberCacheGate)
            {
                if (MemberCache.TryGetValue(key, out var cached))
                {
                    return cached;
                }

                if (MissingMemberCache.Contains(key))
                {
                    return null;
                }
            }

            MemberInfo member = type.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (member == null)
            {
                member = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            }

            lock (MemberCacheGate)
            {
                if (member == null)
                {
                    MissingMemberCache.Add(key);
                }
                else
                {
                    MemberCache[key] = member;
                }
            }

            return member;
        }
    }

    internal sealed class PlayerSample
    {
        public int id;
        public string profile_id;
        public string account_id;
        public string nickname;
        public string side;
        public string type;
        public bool is_main;
        public string group_id;
        public string team_id;
        public Vec3 position;
        public Vec3 velocity;
        public Vec3 look;
        public string pose;
        public string health_status;
        public bool sprinting;
        public bool prone;
    }

    internal sealed class BotSample
    {
        public int id;
        public string profile_id;
        public string account_id;
        public string nickname;
        public string side;
        public string role;
        public string bot_state;
        public string group_id;
        public string team_id;
        public string zone;
        public Vec3 position;
        public Vec3 velocity;
        public Vec3 look;
        public Vec3 destination;
        public bool has_path;
        public bool have_enemy;
        public bool under_fire;
        public bool in_cover;
        public float distance_to_main;
        public PlayerSample player;
        public UtilityScores utility;
    }

    internal sealed class Vec3
    {
        public float x;
        public float y;
        public float z;
    }
}
