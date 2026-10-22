using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common;
using SPTarkov.Server.Core.Models.Eft.InRaid;
using SPTarkov.Server.Core.Models.Eft.Match;
using SPTarkov.Server.Core.Servers;
using SPTarkov.Server.Core.Utils.Logger;
using System.Text.Json;
using CounterKeyValue = SPTarkov.Server.Core.Models.Eft.Common.Tables.CounterKeyValue;
using Item = SPTarkov.Server.Core.Models.Eft.Common.Tables.Item;

namespace Codex.ScavLifeFramework;

[Injectable]
public sealed class ScavLifeService(SptLogger<ScavLifeService> logger, SaveServer saveServer)
{
    private const string LocalTestProfileId = "local-test";
    private const string ModFolderName = "000-ScavLifeFramework";
    private const int StateSchemaVersion = 5;
    private readonly object _gate = new();
    private readonly Dictionary<string, ScavLifeRaidContext> _raidContextsByProfileId = new(StringComparer.OrdinalIgnoreCase);
    private bool _initialized;
    private ScavLifeConfig _config = new();
    private ScavLifeState _state = new();

    private static readonly string[] Archetypes =
    [
        "local",
        "scrounger",
        "courier",
        "lookout",
        "medic",
        "fixer",
        "bruiser",
        "survivor"
    ];

    private static readonly string[] HomeMaps =
    [
        "tarkovstreets",
        "sandbox",
        "sandbox_high",
        "factory4_day",
        "woods",
        "bigmap",
        "interchange",
        "shoreline",
        "lighthouse",
        "rezervbase"
    ];

    private static readonly string[] Temperaments =
    [
        "cautious",
        "opportunist",
        "evasive",
        "stubborn",
        "loyal",
        "desperate"
    ];

    private static readonly string[] Voices =
    [
        "quiet",
        "nervous",
        "mumbling",
        "swagger",
        "angry"
    ];

    private static readonly string[] OutfitPresets =
    [
        "scrapper",
        "worker",
        "hooded",
        "ex-security",
        "field-medic"
    ];

    private static readonly string[] PrimaryWeaponPreferences =
    [
        "whatever-runs",
        "shotgun",
        "smg",
        "rifle",
        "marksman",
        "pistol"
    ];

    private static readonly string[] ArmorPreferences =
    [
        "none",
        "light",
        "balanced",
        "helmet-first"
    ];

    private static readonly string[] BackpackPreferences =
    [
        "pockets-only",
        "small-pack",
        "large-pack"
    ];

    private static readonly string[] MedicalPreferences =
    [
        "cheap-bandages",
        "balanced",
        "painkiller-first"
    ];

    private static readonly string[] LootFocusPreferences =
    [
        "food",
        "medicine",
        "hardware",
        "weapons",
        "valuables"
    ];

    private static readonly string[] RandomNames =
    [
        "Anton",
        "Dima",
        "Ilya",
        "Maks",
        "Pavel",
        "Rinat",
        "Sasha",
        "Vadim",
        "Yarik"
    ];

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true
    };

    private static string ModRoot => Path.Combine(Environment.CurrentDirectory, "user", "mods", ModFolderName);
    private static string ConfigPath => Path.Combine(ModRoot, "config", "config.json");
    private static string StatePath => Path.Combine(ModRoot, "data", "scav_life_state.json");
    private static string PostRaidAuditDirectory => Path.Combine(ModRoot, "data", "post_raid_audit");

    public void Initialize()
    {
        lock (_gate)
        {
            if (_initialized)
            {
                return;
            }

            Directory.CreateDirectory(Path.GetDirectoryName(ConfigPath)!);
            Directory.CreateDirectory(Path.GetDirectoryName(StatePath)!);

            _config = LoadOrCreate(ConfigPath, new ScavLifeConfig());
            _config.Diagnostics ??= new ScavLifeDiagnosticsConfig();
            _state = LoadOrCreate(StatePath, new ScavLifeState());
            _initialized = true;

            var migrated = false;
            if (_state.SchemaVersion < StateSchemaVersion)
            {
                _state.SchemaVersion = StateSchemaVersion;
                migrated = true;
            }

            foreach (var profile in _state.Profiles.Values)
            {
                migrated |= EnsureProfileShape(profile);
            }

            if (migrated)
            {
                SaveState();
            }

            logger.Success($"Scav Life Framework state loaded from {StatePath}.", null);
        }
    }

    public ScavLifeStatusResponse GetStatus(string profileId)
    {
        lock (_gate)
        {
            EnsureInitialized();
            var profile = EnsureProfile(profileId);
            RefreshLifecycle(profile);
            SaveState();
            return BuildStatus(profile);
        }
    }

    public ScavLifeDossierResponse GetDossier(string profileId)
    {
        lock (_gate)
        {
            EnsureInitialized();
            var profile = EnsureProfile(profileId);
            RefreshLifecycle(profile);
            SaveState();
            return BuildDossier(profile);
        }
    }

    public ScavLifeRaidPlanResponse GetRaidPlan(string profileId, string? requestedLocation)
    {
        lock (_gate)
        {
            EnsureInitialized();
            var profile = EnsureProfile(profileId);
            RefreshLifecycle(profile);
            SaveState();
            return BuildRaidPlan(profile, requestedLocation);
        }
    }

    public ScavLifeStashStatusResponse GetStashStatus(string profileId)
    {
        lock (_gate)
        {
            EnsureInitialized();
            var profile = EnsureProfile(profileId);
            RefreshLifecycle(profile);
            SaveState();
            return BuildStashStatus(profile);
        }
    }

    public ScavLifeStashDecisionResponse DecidePendingHaul(string profileId, ScavLifeStashDecisionRequest request)
    {
        lock (_gate)
        {
            EnsureInitialized();
            var profile = EnsureProfile(profileId);
            RefreshLifecycle(profile);

            var destination = NormalizeDestination(request.Destination);
            if (string.IsNullOrWhiteSpace(destination))
            {
                return BuildStashDecision(profile, false, "Destination must be scav-stash, pmc-stash, or fence.");
            }

            var haul = profile.PendingHauls.FirstOrDefault(candidate =>
                string.Equals(candidate.Id, request.PendingHaulId, StringComparison.OrdinalIgnoreCase));
            if (haul is null)
            {
                return BuildStashDecision(profile, false, "Pending haul was not found.");
            }

            var requestedIds = (request.ItemIds ?? [])
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .Select(id => id.Trim())
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            var selected = haul.Items
                .Where(item => requestedIds.Count == 0 || requestedIds.Contains(item.Id))
                .ToList();

            if (selected.Count == 0)
            {
                return BuildStashDecision(profile, false, "No matching pending haul items were selected.");
            }

            if (destination == "scav-stash")
            {
                var maxStored = Math.Max(0, _config.Stash.MaxStoredItemTrees);
                var freeSlots = maxStored <= 0 ? selected.Count : Math.Max(0, maxStored - profile.Stash.Items.Count);
                if (freeSlots <= 0)
                {
                    return BuildStashDecision(profile, false, "Scav Life stash is full; no pending items were moved.");
                }

                selected = selected.Take(freeSlots).ToList();
                if (!TryRemoveSelectedItemsFromPmcProfile(profile.ProfileId, selected, out var removalMessage))
                {
                    return BuildStashDecision(profile, false, removalMessage);
                }

                foreach (var pendingItem in selected)
                {
                    profile.Stash.Items.Add(CloneForStash(pendingItem));
                }
            }

            var selectedIds = selected.Select(item => item.Id).ToHashSet(StringComparer.OrdinalIgnoreCase);
            haul.Items.RemoveAll(item => selectedIds.Contains(item.Id));
            haul.Decisions.Add(new ScavLifeHaulDecision
            {
                Destination = destination,
                ItemIds = [.. selectedIds],
                DecidedAtUnixTime = Now()
            });
            RefreshHaulCounts(haul);
            if (haul.Items.Count == 0)
            {
                haul.Status = "allocated";
            }

            profile.LastUpdatedUnixTime = Now();
            SaveState();

            var skipped = requestedIds.Count > 0 ? requestedIds.Count - selectedIds.Count : 0;
            var message = destination switch
            {
                "scav-stash" when skipped > 0 => $"Moved {selected.Count} item trees to the Scav Life stash; {skipped} selected items were skipped.",
                "scav-stash" => $"Moved {selected.Count} item trees to the Scav Life stash.",
                "pmc-stash" => $"Marked {selected.Count} item trees as sent through the vanilla PMC stash flow.",
                "fence" => $"Marked {selected.Count} item trees as sold through the vanilla Fence flow.",
                _ => $"Recorded {selected.Count} item tree decisions."
            };

            return BuildStashDecision(profile, true, message);
        }
    }

    public ScavLifeCustomizationOptionsResponse GetCustomizationOptions()
    {
        lock (_gate)
        {
            EnsureInitialized();
            return new ScavLifeCustomizationOptionsResponse
            {
                Archetypes = [.. Archetypes],
                HomeMaps = [.. HomeMaps],
                Temperaments = [.. Temperaments],
                Voices = [.. Voices],
                OutfitPresets = [.. OutfitPresets],
                KitPreferences = new ScavLifeKitPreferenceOptions
                {
                    PrimaryWeapons = [.. PrimaryWeaponPreferences],
                    Armor = [.. ArmorPreferences],
                    Backpacks = [.. BackpackPreferences],
                    Medical = [.. MedicalPreferences],
                    LootFocus = [.. LootFocusPreferences]
                }
            };
        }
    }

    public ScavLifeActionResponse Seed(string profileId, string? nickname, bool force)
    {
        lock (_gate)
        {
            EnsureInitialized();
            if (!_config.DevelopmentMode)
            {
                throw new InvalidOperationException("Debug state mutations require developmentMode=true in the Scav Life config.");
            }
            var changed = false;
            var profile = EnsureProfile(profileId);

            if (force || string.IsNullOrWhiteSpace(profile.ActiveScav.Id))
            {
                profile.Generation++;
                profile.ActiveScav = CreateScav(profile.ProfileId, profile.Generation, nickname);
                profile.LastUpdatedUnixTime = Now();
                changed = true;
                SaveState();
            }

            return new ScavLifeActionResponse
            {
                Action = "seed",
                ProfileId = profile.ProfileId,
                Changed = changed,
                Message = changed ? "Seeded active test scav." : "Existing active scav kept; pass force=true to replace.",
                Status = BuildStatus(profile)
            };
        }
    }

    public ScavLifeActionResponse CompleteRun(string profileId, ScavLifeCompleteRunRequest request)
    {
        lock (_gate)
        {
            EnsureInitialized();
            if (!_config.DevelopmentMode)
            {
                throw new InvalidOperationException("Debug state mutations require developmentMode=true in the Scav Life config.");
            }
            var profile = EnsureProfile(profileId);
            return CompleteRunLocked(profile, request, "manual", null);
        }
    }

    public void RecordRaidStart(MongoId sessionId, StartLocalRaidRequestData? request)
    {
        try
        {
            if (request is null || !IsScavSide(request.PlayerSide))
            {
                return;
            }

            lock (_gate)
            {
                EnsureInitialized();
                if (!_config.Enabled)
                {
                    return;
                }

                var profileId = ResolveProfileId(sessionId, null);
                _raidContextsByProfileId[profileId] = new ScavLifeRaidContext
                {
                    Location = CleanLocation(request.Location),
                    ServerId = request.ServerId ?? "",
                    PlayerSide = request.PlayerSide ?? "",
                    StartedAtUnixTime = Now()
                };
            }
        }
        catch (Exception ex)
        {
            logger.Warning("Scav Life could not record scav raid start context.", ex);
        }
    }

    public void CapturePostRaidScav(MongoId sessionId, ScavSaveRequestData? offRaidProfileData)
    {
        try
        {
            if (offRaidProfileData is null || offRaidProfileData.IsPmc == true)
            {
                return;
            }

            lock (_gate)
            {
                EnsureInitialized();
                if (!_config.Enabled)
                {
                    return;
                }

                var profileId = ResolveProfileId(sessionId, null);
                _raidContextsByProfileId.TryGetValue(profileId, out var raidContext);
                _raidContextsByProfileId.Remove(profileId);

                var capture = BuildCaptureRequest(profileId, offRaidProfileData, raidContext);
                if (capture is null)
                {
                    logger.Warning("Scav Life saw a scav post-raid save but could not determine the outcome; state was left unchanged.", null);
                    return;
                }

                var profile = EnsureProfile(profileId);
                if (!string.IsNullOrWhiteSpace(capture.CaptureKey)
                    && string.Equals(profile.Dossier.LastCaptureKey, capture.CaptureKey, StringComparison.Ordinal))
                {
                    logger.Info($"Scav Life ignored duplicate post-raid capture for profile {profileId}.", null);
                    return;
                }

                CompleteRunLocked(profile, capture.Request, "post-raid", capture.CaptureKey);
                var pendingHaul = capture.Request.Survived
                    ? CaptureSurvivedHaul(profile, capture, offRaidProfileData)
                    : null;

                logger.Info(
                    "Scav Life captured post-raid scav result for " +
                    $"{profileId}: {profile.Dossier.LastOutcome} on {profile.Dossier.LastRaidLocation}, " +
                    $"{profile.Dossier.LastRaidKills} kills, {profile.Dossier.LastRaidItemsExtracted} found-in-raid items, " +
                    $"classification={capture.Assessment.Reason}" +
                    (pendingHaul is null ? "." : $", {pendingHaul.ItemTreeCount} pending scav-stash item trees."),
                    null);
            }
        }
        catch (Exception ex)
        {
            logger.Warning("Scav Life post-raid capture failed; SPT save flow was allowed to continue.", ex);
        }
    }

    public ScavLifeActionResponse Customize(string profileId, ScavLifeCustomizeRequest request)
    {
        lock (_gate)
        {
            EnsureInitialized();
            var profile = EnsureProfile(profileId);
            RefreshLifecycle(profile);

            var changed = ApplyCustomizationRequest(profile.ActiveScav, request);
            if (changed)
            {
                profile.LastUpdatedUnixTime = Now();
                SaveState();
            }

            return new ScavLifeActionResponse
            {
                Action = "customize",
                ProfileId = profile.ProfileId,
                Changed = changed,
                Message = changed
                    ? "Scav customization saved to Scav Life state; SPT will keep generating the live scav normally."
                    : "Scav customization already matched the request.",
                Status = BuildStatus(profile)
            };
        }
    }

    public ScavLifeActionResponse RandomizeCustomization(string profileId, ScavLifeRandomizeCustomizationRequest request)
    {
        var nickname = string.IsNullOrWhiteSpace(request.Nickname)
            ? $"{Pick(RandomNames)}-{Random.Shared.Next(10, 99)}"
            : request.Nickname;

        var customizeRequest = new ScavLifeCustomizeRequest
        {
            Nickname = nickname,
            Archetype = Pick(Archetypes),
            HomeMap = Pick(HomeMaps),
            Temperament = Pick(Temperaments),
            Voice = Pick(Voices),
            OutfitPreset = Pick(OutfitPresets),
            Tags =
            [
                "custom",
                "persistent",
                Pick(["transit-ready", "low-profile", "stash-run", "close-range"])
            ],
            KitPreferences = new ScavLifeKitPreferencesRequest
            {
                PrimaryWeapon = Pick(PrimaryWeaponPreferences),
                Armor = Pick(ArmorPreferences),
                Backpack = Pick(BackpackPreferences),
                Medical = Pick(MedicalPreferences),
                LootFocus = Pick(LootFocusPreferences)
            }
        };

        var response = Customize(profileId, customizeRequest);
        response.Action = "randomize-customization";
        response.Message = "Randomized scav customization saved to Scav Life state; SPT will keep generating the live scav normally.";
        return response;
    }

    public ScavLifeActionResponse Reset(string profileId)
    {
        lock (_gate)
        {
            EnsureInitialized();
            if (!_config.DevelopmentMode)
            {
                throw new InvalidOperationException("Debug state mutations require developmentMode=true in the Scav Life config.");
            }
            _state.Profiles.Remove(profileId);
            var profile = EnsureProfile(profileId);
            SaveState();

            return new ScavLifeActionResponse
            {
                Action = "reset",
                ProfileId = profile.ProfileId,
                Changed = true,
                Message = "Scav Life test state reset for profile.",
                Status = BuildStatus(profile)
            };
        }
    }

    public void SyncLiveScavProfile(MongoId sessionId, PmcData? liveScavProfile)
    {
        if (liveScavProfile?.Info is null)
        {
            return;
        }

        lock (_gate)
        {
            EnsureInitialized();
            if (!_config.Enabled || !_config.Customization.SyncToLivePlayerScav)
            {
                return;
            }

            var profile = EnsureProfile(ResolveProfileId(sessionId, null), out var stateChanged);
            stateChanged |= RefreshLifecycle(profile);

            var nickname = SanitizeText(profile.ActiveScav.Nickname, 24);
            if (!string.IsNullOrWhiteSpace(nickname))
            {
                liveScavProfile.Info.Nickname = nickname;
                liveScavProfile.Info.LowerNickname = nickname.ToLowerInvariant();
            }

            if (_config.Customization.ApplyLevelAndExperienceToLiveScav)
            {
                liveScavProfile.Info.Level = Math.Max(1, profile.ActiveScav.Level);
                liveScavProfile.Info.Experience = Math.Max(0, profile.ActiveScav.Experience);
            }

            if (stateChanged)
            {
                SaveState();
            }
        }
    }

    public static string ResolveProfileId(MongoId sessionId, string? requestedProfileId)
    {
        if (!string.IsNullOrWhiteSpace(requestedProfileId))
        {
            return requestedProfileId.Trim();
        }

        var session = sessionId.ToString();
        return string.IsNullOrWhiteSpace(session) || session == "000000000000000000000000"
            ? LocalTestProfileId
            : session;
    }

    private void EnsureInitialized()
    {
        if (!_initialized)
        {
            Initialize();
        }
    }

    private ScavLifeProfileState EnsureProfile(string profileId)
    {
        return EnsureProfile(profileId, out _);
    }

    private ScavLifeProfileState EnsureProfile(string profileId, out bool changed)
    {
        changed = false;
        profileId = string.IsNullOrWhiteSpace(profileId) ? LocalTestProfileId : profileId.Trim();
        if (_state.Profiles.TryGetValue(profileId, out var profile))
        {
            changed = EnsureProfileShape(profile);
            return profile;
        }

        var now = Now();
        profile = new ScavLifeProfileState
        {
            ProfileId = profileId,
            Generation = 1,
            CreatedAtUnixTime = now,
            LastUpdatedUnixTime = now,
            ActiveScav = CreateScav(profileId, 1, _config.StartingScav.Nickname),
            Stash = new ScavLifeStash
            {
                Width = _config.Stash.Width,
                Height = _config.Stash.Height,
                Items = []
            }
        };

        _state.Profiles[profileId] = profile;
        changed = true;
        return profile;
    }

    private ScavLifeScav CreateScav(string profileId, int generation, string? nickname)
    {
        var now = Now();
        return new ScavLifeScav
        {
            Id = $"scavlife-{profileId}-{generation}",
            Nickname = string.IsNullOrWhiteSpace(nickname) ? _config.StartingScav.Nickname : nickname.Trim(),
            Alive = true,
            ReadyAtUnixTime = now,
            Level = Math.Max(1, _config.StartingScav.Level),
            Experience = Math.Max(0, _config.StartingScav.Experience),
            LastLocation = "hideout",
            Customization = CreateDefaultCustomization(nickname)
        };
    }

    private bool RefreshLifecycle(ScavLifeProfileState profile)
    {
        if (profile.ActiveScav.Alive || profile.ActiveScav.ReadyAtUnixTime > Now())
        {
            return false;
        }

        profile.Generation++;
        profile.ActiveScav = CreateScav(profile.ProfileId, profile.Generation, _config.StartingScav.Nickname);
        profile.Dossier.SurvivalStreak = 0;
        profile.Dossier.Stress = Clamp(profile.Dossier.Stress - 20, 0, 100);
        profile.Dossier.Fatigue = Clamp(profile.Dossier.Fatigue - 30, 0, 100);
        profile.Dossier.LastOutcome = "replacement-ready";
        profile.LastUpdatedUnixTime = Now();
        return true;
    }

    private ScavLifeStatusResponse BuildStatus(ScavLifeProfileState profile)
    {
        var now = Now();
        return new ScavLifeStatusResponse
        {
            Enabled = _config.Enabled,
            DevelopmentMode = _config.DevelopmentMode,
            ProfileId = profile.ProfileId,
            CanDeploy = _config.Enabled && profile.ActiveScav.Alive && profile.ActiveScav.ReadyAtUnixTime <= now,
            ServerUnixTime = now,
            Profile = profile
        };
    }

    private ScavLifeDossierResponse BuildDossier(ScavLifeProfileState profile)
    {
        var now = Now();
        var canDeploy = _config.Enabled && profile.ActiveScav.Alive && profile.ActiveScav.ReadyAtUnixTime <= now;
        var condition = GetCondition(profile, now);

        return new ScavLifeDossierResponse
        {
            ProfileId = profile.ProfileId,
            ServerUnixTime = now,
            CanDeploy = canDeploy,
            Condition = condition,
            Summary = BuildDossierSummary(profile, condition),
            Dossier = profile.Dossier
        };
    }

    private ScavLifeRaidPlanResponse BuildRaidPlan(ScavLifeProfileState profile, string? requestedLocation)
    {
        var now = Now();
        var customization = profile.ActiveScav.Customization ?? CreateDefaultCustomization(profile.ActiveScav.Nickname);
        var kit = customization.KitPreferences ?? new ScavLifeKitPreferences();
        var suggestedMap = GetAllowedValue(
            string.IsNullOrWhiteSpace(requestedLocation) ? customization.HomeMap : requestedLocation,
            HomeMaps);
        var canDeploy = _config.Enabled && profile.ActiveScav.Alive && profile.ActiveScav.ReadyAtUnixTime <= now;
        var riskScore = profile.Dossier.Stress + profile.Dossier.Fatigue - (profile.Dossier.Trust / 2);
        if (!canDeploy)
        {
            riskScore += 50;
        }

        var objectives = BuildObjectives(profile, kit, suggestedMap);
        var avoid = BuildAvoidList(profile, kit);

        return new ScavLifeRaidPlanResponse
        {
            ProfileId = profile.ProfileId,
            ServerUnixTime = now,
            CanDeploy = canDeploy,
            SuggestedMap = suggestedMap,
            RiskLevel = GetRiskLevel(riskScore),
            Role = customization.Archetype,
            ExtractionStyle = GetExtractionStyle(customization.Temperament, profile.Dossier),
            Objectives = objectives,
            Avoid = avoid,
            LoadoutPlan = new ScavLifeLoadoutPlan
            {
                PrimaryWeapon = kit.PrimaryWeapon,
                Armor = kit.Armor,
                Backpack = kit.Backpack,
                Medical = kit.Medical,
                LootFocus = kit.LootFocus,
                BudgetTier = GetBudgetTier(profile)
            },
            Dossier = profile.Dossier
        };
    }

    private ScavLifeStashStatusResponse BuildStashStatus(ScavLifeProfileState profile)
    {
        return new ScavLifeStashStatusResponse
        {
            ProfileId = profile.ProfileId,
            ServerUnixTime = Now(),
            Rules = new ScavLifeStashRuleSummary
            {
                CaptureSurvivedHauls = _config.Stash.CaptureSurvivedHauls,
                AutoStoreSurvivedHauls = _config.Stash.AutoStoreSurvivedHauls,
                MaxPendingHauls = _config.Stash.MaxPendingHauls,
                MaxStoredItemTrees = _config.Stash.MaxStoredItemTrees
            },
            Stash = profile.Stash,
            PendingHauls = profile.PendingHauls
        };
    }

    private ScavLifeStashDecisionResponse BuildStashDecision(ScavLifeProfileState profile, bool changed, string message)
    {
        return new ScavLifeStashDecisionResponse
        {
            ProfileId = profile.ProfileId,
            Changed = changed,
            Message = message,
            Status = BuildStashStatus(profile)
        };
    }

    private ScavLifeActionResponse CompleteRunLocked(
        ScavLifeProfileState profile,
        ScavLifeCompleteRunRequest request,
        string captureSource,
        string? captureKey)
    {
        RefreshLifecycle(profile);

        profile.Stats.RunsStarted++;
        profile.Stats.ItemsExtracted += Math.Max(0, request.ItemsExtracted);
        profile.Stats.Kills += Math.Max(0, request.Kills);
        profile.Stats.TotalLootValue += Math.Max(0, request.LootValue);
        profile.ActiveScav.LastLocation = string.IsNullOrWhiteSpace(request.Location) ? "unknown" : request.Location.Trim();

        var lootExperience = (int)Math.Round(Math.Max(0, request.LootValue) * _config.Progression.LootValueToExperienceRatio);
        if (request.Survived)
        {
            profile.Stats.RunsSurvived++;
            profile.ActiveScav.Alive = true;
            profile.ActiveScav.Experience += _config.Progression.SurvivedRunExperience + lootExperience;
            profile.ActiveScav.ReadyAtUnixTime = Now() + MinutesToSeconds(_config.Cooldowns.SurvivedMinutes);
            UpdateDossierForRun(profile, request, survived: true, captureSource, captureKey);
        }
        else
        {
            profile.Stats.RunsFailed++;
            profile.ActiveScav.Alive = false;
            profile.ActiveScav.Experience += _config.Progression.DeathRunExperience;
            profile.ActiveScav.ReadyAtUnixTime = Now() + MinutesToSeconds(_config.Cooldowns.DeathMinutes);
            UpdateDossierForRun(profile, request, survived: false, captureSource, captureKey);
        }

        profile.ActiveScav.Level = CalculateLevel(profile.ActiveScav.Experience);
        profile.LastUpdatedUnixTime = Now();
        SaveState();

        return new ScavLifeActionResponse
        {
            Action = captureSource == "post-raid" ? "post-raid-capture" : "complete-run",
            ProfileId = profile.ProfileId,
            Changed = true,
            Message = request.Survived
                ? "Run marked survived; same scav remains persistent."
                : "Run marked failed; replacement scav will appear after cooldown.",
            Status = BuildStatus(profile)
        };
    }

    private ScavLifePostRaidCapture? BuildCaptureRequest(
        string profileId,
        ScavSaveRequestData offRaidProfileData,
        ScavLifeRaidContext? raidContext)
    {
        var location = FirstNonBlank(
            raidContext?.Location,
            offRaidProfileData.Info?.EntryPoint,
            ReadExtensionString(offRaidProfileData.ExtensionData, "location"),
            ReadExtensionString(offRaidProfileData.ExtensionData, "Location"),
            "unknown");

        var kills = CountVictims(offRaidProfileData);
        var itemsExtracted = CountFoundInRaidItems(offRaidProfileData);
        var lootValue = EstimateLootValue(offRaidProfileData);
        var lastSessionDate = offRaidProfileData.Stats?.Eft?.LastSessionDate ?? 0;
        var sessionExperience = offRaidProfileData.Stats?.Eft?.TotalSessionExperience ?? 0;
        var assessment = AssessSurvival(offRaidProfileData);
        if (assessment.Survived is null)
        {
            WritePostRaidAudit(profileId, offRaidProfileData, raidContext, assessment, null, location, kills, itemsExtracted, lootValue);
            return null;
        }

        var contextKey = FirstNonBlank(
            raidContext?.ServerId,
            raidContext?.StartedAtUnixTime > 0 ? raidContext.StartedAtUnixTime.ToString() : null,
            "no-context");
        var captureKey = string.Join(
            ":",
            profileId,
            contextKey,
            lastSessionDate,
            assessment.Survived.Value ? "survived" : "failed",
            Normalize(location),
            kills,
            itemsExtracted,
            Math.Round(sessionExperience));

        var capture = new ScavLifePostRaidCapture(
            captureKey,
            new ScavLifeCompleteRunRequest
            {
                ProfileId = profileId,
                Survived = assessment.Survived.Value,
                Location = location,
                LootValue = lootValue,
                ItemsExtracted = itemsExtracted,
                Kills = kills
            },
            assessment);

        WritePostRaidAudit(profileId, offRaidProfileData, raidContext, assessment, capture, location, kills, itemsExtracted, lootValue);
        return capture;
    }

    private ScavLifePendingHaul? CaptureSurvivedHaul(
        ScavLifeProfileState profile,
        ScavLifePostRaidCapture capture,
        ScavSaveRequestData offRaidProfileData)
    {
        if (!_config.Stash.CaptureSurvivedHauls)
        {
            return null;
        }

        var now = Now();
        var haulId = NewLedgerId("haul");
        var items = BuildExtractedItemTrees(haulId, now, offRaidProfileData);
        if (items.Count == 0)
        {
            logger.Info("Scav Life classified a scav raid as survived, but no extracted item roots were available for the pending stash haul.", null);
            return null;
        }

        var haul = new ScavLifePendingHaul
        {
            Id = haulId,
            CaptureKey = capture.CaptureKey,
            Location = string.IsNullOrWhiteSpace(capture.Request.Location) ? "unknown" : capture.Request.Location.Trim(),
            Status = _config.Stash.AutoStoreSurvivedHauls ? "allocated" : "pending",
            CapturedAtUnixTime = now,
            Items = items
        };
        RefreshHaulCounts(haul);

        profile.PendingHauls.RemoveAll(existing =>
            string.Equals(existing.CaptureKey, capture.CaptureKey, StringComparison.Ordinal));

        if (_config.Stash.AutoStoreSurvivedHauls)
        {
            var selected = items.Take(GetFreeScavStashSlots(profile)).ToList();
            foreach (var item in selected)
            {
                profile.Stash.Items.Add(CloneForStash(item));
            }

            haul.Decisions.Add(new ScavLifeHaulDecision
            {
                Destination = "scav-stash",
                ItemIds = selected.Select(item => item.Id).ToList(),
                DecidedAtUnixTime = now
            });
            haul.Items.RemoveAll(item => selected.Any(selectedItem => selectedItem.Id == item.Id));
            RefreshHaulCounts(haul);
            if (haul.Items.Count > 0)
            {
                haul.Status = "pending";
                profile.PendingHauls.Insert(0, haul);
            }
        }
        else
        {
            profile.PendingHauls.Insert(0, haul);
        }

        PrunePendingHauls(profile);
        profile.LastUpdatedUnixTime = now;
        SaveState();
        return haul;
    }

    private void WritePostRaidAudit(
        string profileId,
        ScavSaveRequestData offRaidProfileData,
        ScavLifeRaidContext? raidContext,
        ScavLifeSurvivalAssessment assessment,
        ScavLifePostRaidCapture? capture,
        string location,
        int kills,
        int itemsExtracted,
        int lootValue)
    {
        if (!_config.Diagnostics.WritePostRaidAudit)
        {
            return;
        }

        try
        {
            Directory.CreateDirectory(PostRaidAuditDirectory);
            var counters = GetSessionCounters(offRaidProfileData).ToList();
            var roots = GetExtractedGearRoots(offRaidProfileData);
            var inventoryItems = offRaidProfileData.Inventory?.Items;
            var outcome = assessment.Survived is null ? "unknown" : assessment.Survived.Value ? "survived" : "failed";
            var fileName = $"{DateTimeOffset.UtcNow:yyyyMMdd-HHmmss}-{SafeFileToken(profileId)}-{outcome}-{Guid.NewGuid().ToString("N")[..8]}.json";
            var audit = new
            {
                Mod = "Scav Life Framework",
                Version = "0.5.1",
                WrittenAtUtc = DateTimeOffset.UtcNow.ToString("O"),
                ProfileId = profileId,
                Outcome = outcome,
                Capture = capture is null
                    ? null
                    : new
                    {
                        capture.CaptureKey,
                        capture.Request.Survived,
                        capture.Request.Location,
                        capture.Request.LootValue,
                        capture.Request.ItemsExtracted,
                        capture.Request.Kills
                    },
                RaidContext = raidContext is null
                    ? null
                    : new
                    {
                        raidContext.Location,
                        raidContext.ServerId,
                        raidContext.PlayerSide,
                        raidContext.StartedAtUnixTime
                    },
                Classification = assessment,
                Summary = new
                {
                    Location = location,
                    Kills = kills,
                    ItemsExtracted = itemsExtracted,
                    LootValue = lootValue
                },
                Info = new
                {
                    EntryPoint = offRaidProfileData.Info?.EntryPoint ?? ""
                },
                Stats = new
                {
                    LastSessionDate = offRaidProfileData.Stats?.Eft?.LastSessionDate ?? 0,
                    TotalSessionExperience = offRaidProfileData.Stats?.Eft?.TotalSessionExperience ?? 0,
                    VictimCount = offRaidProfileData.Stats?.Eft?.Victims?.Count() ?? 0,
                    FoundInRaidItemCount = CountFoundInRaidItems(offRaidProfileData),
                    DeathCause = assessment.DeathCauseSummary
                },
                Inventory = new
                {
                    EquipmentId = offRaidProfileData.Inventory?.Equipment?.ToString() ?? "",
                    ItemCount = inventoryItems?.Count ?? 0,
                    ExtractedRootItemCount = roots.Count,
                    ExtractedRootItems = roots.Take(80).Select(BuildAuditItem).ToList()
                },
                SessionCounters = BuildCounterAudit(counters),
                ExtensionData = BuildExtensionDataAudit(offRaidProfileData.ExtensionData)
            };

            var path = Path.Combine(PostRaidAuditDirectory, fileName);
            File.WriteAllText(path, JsonSerializer.Serialize(audit, JsonOptions));
            PrunePostRaidAuditFiles();
        }
        catch (Exception ex)
        {
            logger.Warning("Scav Life could not write post-raid audit file.", ex);
        }
    }

    private void PrunePostRaidAuditFiles()
    {
        var maxFiles = Math.Max(0, _config.Diagnostics.MaxPostRaidAuditFiles);
        if (maxFiles <= 0 || !Directory.Exists(PostRaidAuditDirectory))
        {
            return;
        }

        foreach (var file in new DirectoryInfo(PostRaidAuditDirectory)
            .GetFiles("*.json")
            .OrderByDescending(file => file.LastWriteTimeUtc)
            .Skip(maxFiles))
        {
            try
            {
                file.Delete();
            }
            catch
            {
                // Audit pruning should never block profile save.
            }
        }
    }

    private static object BuildAuditItem(Item item)
    {
        return new
        {
            Id = item.Id.ToString(),
            TemplateId = item.Template.ToString(),
            ParentId = item.ParentId ?? "",
            SlotId = item.SlotId ?? "",
            StackCount = GetStackCount(item)
        };
    }

    private static List<object> BuildCounterAudit(IEnumerable<CounterKeyValue> counters)
    {
        var result = new List<object>();
        foreach (var counter in counters)
        {
            var keys = (counter.Key ?? []).ToList();
            var value = counter.Value ?? 0;
            if (value <= 0 && !keys.Any(IsAuditCounterKey))
            {
                continue;
            }

            result.Add(new
            {
                Keys = keys,
                Value = value
            });

            if (result.Count >= 200)
            {
                break;
            }
        }

        return result;
    }

    private static bool IsAuditCounterKey(string key)
    {
        return key.Contains("ExitStatus", StringComparison.OrdinalIgnoreCase)
            || key.Contains("Deaths", StringComparison.OrdinalIgnoreCase)
            || key.Contains("Exp", StringComparison.OrdinalIgnoreCase)
            || key.Contains("Kills", StringComparison.OrdinalIgnoreCase)
            || key.Contains("Survived", StringComparison.OrdinalIgnoreCase);
    }

    private static Dictionary<string, string> BuildExtensionDataAudit(Dictionary<string, object>? extensionData)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (extensionData is null)
        {
            return result;
        }

        foreach (var (key, value) in extensionData.Take(50))
        {
            result[key] = DescribeJsonValue(value, 600);
        }

        return result;
    }

    private List<ScavLifeStashItem> BuildExtractedItemTrees(string haulId, long capturedAtUnixTime, ScavSaveRequestData offRaidProfileData)
    {
        var inventory = offRaidProfileData.Inventory;
        var inventoryItems = inventory?.Items;
        if (inventoryItems is null || inventoryItems.Count == 0)
        {
            return [];
        }

        var byParent = BuildParentMap(inventoryItems);
        var roots = GetExtractedGearRoots(offRaidProfileData, inventoryItems, byParent);

        var result = new List<ScavLifeStashItem>();
        foreach (var root in roots)
        {
            var tree = BuildItemTree(root, byParent);
            if (tree.Count == 0)
            {
                continue;
            }

            result.Add(new ScavLifeStashItem
            {
                Id = NewLedgerId("pending"),
                TemplateId = root.Template.ToString(),
                StackCount = GetStackCount(root),
                Source = "scav-extract",
                Status = "pending",
                SourceHaulId = haulId,
                OriginalRootItemId = root.Id.ToString(),
                RootParentId = root.ParentId ?? "",
                RootSlotId = root.SlotId ?? "",
                ItemCount = tree.Count,
                CapturedAtUnixTime = capturedAtUnixTime,
                ItemTree = tree
                    .Select(item => JsonSerializer.SerializeToElement(item, JsonOptions).Clone())
                    .ToList()
            });
        }

        return result;
    }

    private static Dictionary<string, List<Item>> BuildParentMap(IEnumerable<Item> inventoryItems)
    {
        return inventoryItems
            .Where(item => !string.IsNullOrWhiteSpace(item.ParentId))
            .GroupBy(item => item.ParentId!, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(group => group.Key, group => group.ToList(), StringComparer.OrdinalIgnoreCase);
    }

    private static List<Item> GetExtractedGearRoots(ScavSaveRequestData offRaidProfileData)
    {
        var inventoryItems = offRaidProfileData.Inventory?.Items;
        if (inventoryItems is null || inventoryItems.Count == 0)
        {
            return [];
        }

        return GetExtractedGearRoots(offRaidProfileData, inventoryItems, BuildParentMap(inventoryItems));
    }

    private static List<Item> GetExtractedGearRoots(
        ScavSaveRequestData offRaidProfileData,
        List<Item> inventoryItems,
        Dictionary<string, List<Item>> byParent)
    {
        var equipmentId = offRaidProfileData.Inventory?.Equipment?.ToString() ?? "";
        var directRoots = !string.IsNullOrWhiteSpace(equipmentId)
            ? inventoryItems
                .Where(item => string.Equals(item.ParentId, equipmentId, StringComparison.OrdinalIgnoreCase))
                .Where(IsExtractedGearRoot)
                .ToList()
            : inventoryItems
                .Where(item => IsExtractedGearRoot(item) && !inventoryItems.Any(parent =>
                    string.Equals(parent.Id.ToString(), item.ParentId, StringComparison.OrdinalIgnoreCase)))
                .ToList();

        return ExpandVirtualCarryContainers(directRoots, byParent);
    }

    private static List<Item> ExpandVirtualCarryContainers(List<Item> directRoots, Dictionary<string, List<Item>> byParent)
    {
        var roots = new List<Item>();
        foreach (var directRoot in directRoots)
        {
            if (!IsVirtualCarryContainer(directRoot))
            {
                roots.Add(directRoot);
                continue;
            }

            if (!byParent.TryGetValue(directRoot.Id.ToString(), out var children))
            {
                continue;
            }

            roots.AddRange(children.Where(IsExtractedGearRoot));
        }

        return roots;
    }

    private static List<Item> BuildItemTree(Item root, Dictionary<string, List<Item>> byParent)
    {
        var result = new List<Item>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var stack = new Stack<Item>();
        stack.Push(root);

        while (stack.Count > 0)
        {
            var current = stack.Pop();
            var currentId = current.Id.ToString();
            if (!seen.Add(currentId))
            {
                continue;
            }

            result.Add(current);
            if (!byParent.TryGetValue(currentId, out var children))
            {
                continue;
            }

            for (var index = children.Count - 1; index >= 0; index--)
            {
                stack.Push(children[index]);
            }
        }

        return result;
    }

    private static bool IsExtractedGearRoot(Item item)
    {
        var slot = Normalize(item.SlotId);
        return slot.Length > 0
            && slot is not "sortingtable"
            && slot is not "stash"
            && slot is not "questraiditems"
            && slot is not "queststashitems";
    }

    private static bool IsVirtualCarryContainer(Item item)
    {
        var slot = Normalize(item.SlotId);
        return slot is "pockets" or "securedcontainer";
    }

    private static int GetStackCount(Item item)
    {
        var count = item.Upd?.StackObjectsCount ?? item.Upd?.OriginalStackObjectsCount ?? 1;
        return Math.Max(1, (int)Math.Round(count));
    }

    private int GetFreeScavStashSlots(ScavLifeProfileState profile)
    {
        var maxStored = Math.Max(0, _config.Stash.MaxStoredItemTrees);
        return maxStored <= 0 ? int.MaxValue : Math.Max(0, maxStored - profile.Stash.Items.Count);
    }

    private static ScavLifeStashItem CloneForStash(ScavLifeStashItem item)
    {
        return new ScavLifeStashItem
        {
            Id = NewLedgerId("stash"),
            TemplateId = item.TemplateId,
            StackCount = Math.Max(1, item.StackCount),
            Source = "scav-extract",
            Status = "stored",
            SourceHaulId = item.SourceHaulId,
            OriginalRootItemId = item.OriginalRootItemId,
            RootParentId = item.RootParentId,
            RootSlotId = item.RootSlotId,
            ItemCount = Math.Max(1, item.ItemCount),
            CapturedAtUnixTime = item.CapturedAtUnixTime,
            ItemTree = (item.ItemTree ?? [])
                .Select(element => element.Clone())
                .ToList()
        };
    }

    private bool TryRemoveSelectedItemsFromPmcProfile(
        string profileId,
        List<ScavLifeStashItem> selected,
        out string message)
    {
        message = "";
        if (selected.Count == 0)
        {
            message = "No selected items were available to move.";
            return false;
        }

        if (!MongoId.IsValidMongoId(profileId))
        {
            message = "Scav stash decisions require a real SPT profile session; local-test cannot mutate a PMC stash.";
            return false;
        }

        try
        {
            var mongoId = new MongoId(profileId);
            if (!saveServer.ProfileExists(mongoId))
            {
                message = "SPT profile was not loaded; no items were moved to avoid duplication.";
                return false;
            }

            var sptProfile = saveServer.GetProfile(mongoId);
            var inventoryItems = sptProfile?.CharacterData?.PmcData?.Inventory?.Items;
            if (inventoryItems is null)
            {
                message = "PMC inventory was not available; no items were moved to avoid duplication.";
                return false;
            }

            var selectedItemIds = selected
                .SelectMany(ExtractSnapshotItemIds)
                .Where(id => !string.IsNullOrWhiteSpace(id))
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            if (selectedItemIds.Count == 0)
            {
                message = "Selected pending items did not contain item IDs; no items were moved.";
                return false;
            }

            var profileItemIds = inventoryItems
                .Select(item => item.Id.ToString())
                .ToHashSet(StringComparer.OrdinalIgnoreCase);
            var missingIds = selectedItemIds
                .Where(id => !profileItemIds.Contains(id))
                .Take(5)
                .ToList();
            if (missingIds.Count > 0)
            {
                message = "Selected items were not found in the PMC stash/profile, so Scav Life refused the move to prevent duplication.";
                return false;
            }

            var removed = inventoryItems.RemoveAll(item => selectedItemIds.Contains(item.Id.ToString()));
            if (removed <= 0)
            {
                message = "No matching PMC profile items were removed; no items were moved to avoid duplication.";
                return false;
            }

            saveServer.SaveProfileAsync(mongoId).GetAwaiter().GetResult();
            return true;
        }
        catch (Exception ex)
        {
            message = $"Could not remove selected items from PMC profile safely: {ex.Message}";
            return false;
        }
    }

    private static IEnumerable<string> ExtractSnapshotItemIds(ScavLifeStashItem item)
    {
        foreach (var element in item.ItemTree ?? [])
        {
            if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty("_id", out var idProperty))
            {
                continue;
            }

            var id = idProperty.GetString();
            if (!string.IsNullOrWhiteSpace(id))
            {
                yield return id;
            }
        }
    }

    private void PrunePendingHauls(ScavLifeProfileState profile)
    {
        var maxPending = Math.Max(1, _config.Stash.MaxPendingHauls);
        if (profile.PendingHauls.Count <= maxPending)
        {
            return;
        }

        profile.PendingHauls.RemoveRange(maxPending, profile.PendingHauls.Count - maxPending);
    }

    private static void RefreshHaulCounts(ScavLifePendingHaul haul)
    {
        haul.Items ??= [];
        haul.Decisions ??= [];
        haul.ItemTreeCount = haul.Items.Count;
        haul.FlatItemCount = haul.Items.Sum(item => Math.Max(1, item.ItemCount));
    }

    private ScavLifeSurvivalAssessment AssessSurvival(ScavSaveRequestData offRaidProfileData)
    {
        var sessionCounters = GetSessionCounters(offRaidProfileData).ToList();
        var exitStatuses = FindExitStatuses(sessionCounters);
        var deaths = GetCounterValue(sessionCounters, "Deaths");
        var exitExperience = GetCounterValue(sessionCounters, "Exp", "ExpExitStatus");
        var totalSessionExperience = offRaidProfileData.Stats?.Eft?.TotalSessionExperience ?? 0;
        var foundInRaidItemCount = CountFoundInRaidItems(offRaidProfileData);
        var inventoryItemCount = offRaidProfileData.Inventory?.Items?.Count ?? 0;
        var extractedRootItemCount = GetExtractedGearRoots(offRaidProfileData).Count;
        var deathCauseSummary = DescribeJsonValue(offRaidProfileData.Stats?.Eft?.DeathCause, 1200);
        var hasMeaningfulDeathCause = HasMeaningfulSerializedJson(deathCauseSummary);

        ScavLifeSurvivalAssessment Build(bool? survived, string reason)
        {
            return new ScavLifeSurvivalAssessment
            {
                Survived = survived,
                Reason = reason,
                ExitStatuses = exitStatuses,
                Deaths = deaths,
                ExitExperience = exitExperience,
                TotalSessionExperience = totalSessionExperience,
                HasMeaningfulDeathCause = hasMeaningfulDeathCause,
                DeathCauseSummary = deathCauseSummary,
                FoundInRaidItemCount = foundInRaidItemCount,
                InventoryItemCount = inventoryItemCount,
                ExtractedRootItemCount = extractedRootItemCount
            };
        }

        if (exitStatuses.Any(IsSuccessfulExitStatus))
        {
            return Build(true, "exit-status-success");
        }

        if (exitExperience > 0 && deaths <= 0 && !hasMeaningfulDeathCause)
        {
            return Build(true, "exit-experience");
        }

        if (deaths > 0)
        {
            return Build(false, "death-counter");
        }

        if (hasMeaningfulDeathCause)
        {
            return Build(false, "death-cause");
        }

        var failedExitStatus = exitStatuses.FirstOrDefault(IsFailedExitStatus);
        if (!string.IsNullOrWhiteSpace(failedExitStatus))
        {
            return Build(false, $"exit-status-{Normalize(failedExitStatus)}");
        }

        if (inventoryItemCount > 0 && extractedRootItemCount > 0)
        {
            return Build(true, "inventory-without-death");
        }

        if (totalSessionExperience > 0 || foundInRaidItemCount > 0)
        {
            return Build(true, "activity-without-death");
        }

        if (exitStatuses.Count > 0)
        {
            var statusSummary = string.Join("-", exitStatuses.Select(Normalize).Where(status => status.Length > 0).Take(3));
            return Build(null, string.IsNullOrWhiteSpace(statusSummary) ? "ambiguous-exit-status" : $"ambiguous-exit-status-{statusSummary}");
        }

        return Build(null, "no-post-raid-outcome-signal");
    }

    private int CountVictims(ScavSaveRequestData offRaidProfileData)
    {
        var victims = offRaidProfileData.Stats?.Eft?.Victims?.Count() ?? 0;
        if (victims > 0)
        {
            return victims;
        }

        return (int)Math.Max(0, Math.Round(GetCounterValue(GetSessionCounters(offRaidProfileData), "Kills")));
    }

    private static int CountFoundInRaidItems(ScavSaveRequestData offRaidProfileData)
    {
        return offRaidProfileData.Stats?.Eft?.FoundInRaidItems?.Count() ?? 0;
    }

    private int EstimateLootValue(ScavSaveRequestData offRaidProfileData)
    {
        if (_config.Progression.LootValueToExperienceRatio <= 0)
        {
            return 0;
        }

        var lootingExperience = GetCounterValue(GetSessionCounters(offRaidProfileData), "Exp", "ExpLooting");
        return lootingExperience <= 0
            ? 0
            : (int)Math.Round(lootingExperience / _config.Progression.LootValueToExperienceRatio);
    }

    private static IEnumerable<CounterKeyValue> GetSessionCounters(ScavSaveRequestData offRaidProfileData)
    {
        return offRaidProfileData.Stats?.Eft?.SessionCounters?.Items ?? [];
    }

    private static List<string> FindExitStatuses(IEnumerable<CounterKeyValue>? counters)
    {
        var statuses = new List<string>();
        foreach (var counter in counters ?? [])
        {
            var keys = counter.Key ?? [];
            if (!keys.Contains("ExitStatus", StringComparer.OrdinalIgnoreCase))
            {
                continue;
            }

            var value = counter.Value ?? 0;
            if (value <= 0)
            {
                continue;
            }

            var status = keys.FirstOrDefault(key => !string.Equals(key, "ExitStatus", StringComparison.OrdinalIgnoreCase)
                && !string.Equals(key, "Scav", StringComparison.OrdinalIgnoreCase)
                && !string.Equals(key, "Pmc", StringComparison.OrdinalIgnoreCase)) ?? "";
            if (!string.IsNullOrWhiteSpace(status) && !statuses.Contains(status, StringComparer.OrdinalIgnoreCase))
            {
                statuses.Add(status);
            }
        }

        return statuses;
    }

    private static string FindExitStatus(IEnumerable<CounterKeyValue>? counters)
    {
        return FindExitStatuses(counters).FirstOrDefault() ?? "";
    }

    private static double GetCounterValue(IEnumerable<CounterKeyValue>? counters, params string[] requiredKeys)
    {
        foreach (var counter in counters ?? [])
        {
            var keys = counter.Key ?? [];
            if (requiredKeys.All(requiredKey => keys.Contains(requiredKey, StringComparer.OrdinalIgnoreCase)))
            {
                return counter.Value ?? 0;
            }
        }

        return 0;
    }

    private static bool IsSuccessfulExitStatus(string exitStatus)
    {
        return exitStatus.Contains("survived", StringComparison.OrdinalIgnoreCase)
            || exitStatus.Contains("runner", StringComparison.OrdinalIgnoreCase)
            || exitStatus.Contains("transit", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsFailedExitStatus(string exitStatus)
    {
        var normalized = Normalize(exitStatus);
        return normalized.Contains("killed", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("dead", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("death", StringComparison.OrdinalIgnoreCase)
            || normalized.Contains("missinginaction", StringComparison.OrdinalIgnoreCase)
            || normalized == "mia";
    }

    private static string DescribeJsonValue(object? value, int maxLength)
    {
        if (value is null)
        {
            return "";
        }

        try
        {
            return Truncate(JsonSerializer.Serialize(value, JsonOptions), maxLength);
        }
        catch
        {
            return Truncate(value.ToString(), maxLength);
        }
    }

    private static bool HasMeaningfulSerializedJson(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(json);
            return JsonHasMeaningfulValue(document.RootElement);
        }
        catch
        {
            var normalized = Normalize(json);
            return normalized.Length > 0
                && normalized is not "null"
                && normalized is not "none"
                && normalized is not "unknown"
                && normalized is not "undefined";
        }
    }

    private static bool JsonHasMeaningfulValue(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.Object => element.EnumerateObject().Any(property => JsonHasMeaningfulValue(property.Value)),
            JsonValueKind.Array => element.EnumerateArray().Any(JsonHasMeaningfulValue),
            JsonValueKind.String => IsMeaningfulText(element.GetString()),
            JsonValueKind.Number => element.TryGetDouble(out var value) && Math.Abs(value) > double.Epsilon,
            JsonValueKind.True => true,
            _ => false
        };
    }

    private static bool IsMeaningfulText(string? text)
    {
        var normalized = Normalize(text);
        return normalized.Length > 0
            && normalized is not "null"
            && normalized is not "none"
            && normalized is not "unknown"
            && normalized is not "undefined";
    }

    private static void UpdateDossierForRun(
        ScavLifeProfileState profile,
        ScavLifeCompleteRunRequest request,
        bool survived,
        string captureSource,
        string? captureKey)
    {
        var dossier = profile.Dossier ??= new ScavLifeDossier();
        dossier.LastOutcome = survived ? "survived" : "failed";
        dossier.LastRaidLocation = string.IsNullOrWhiteSpace(request.Location) ? "unknown" : request.Location.Trim();
        dossier.LastRaidLootValue = Math.Max(0, request.LootValue);
        dossier.LastRaidItemsExtracted = Math.Max(0, request.ItemsExtracted);
        dossier.LastRaidKills = Math.Max(0, request.Kills);
        dossier.LastRaidUnixTime = Now();
        dossier.LastCaptureSource = captureSource;
        dossier.LastCaptureKey = captureKey ?? "";

        if (survived)
        {
            dossier.SurvivalStreak++;
            dossier.BestSurvivalStreak = Math.Max(dossier.BestSurvivalStreak, dossier.SurvivalStreak);
            dossier.Trust = Clamp(dossier.Trust + 2 + Math.Min(8, dossier.LastRaidLootValue / 50000) + Math.Min(3, dossier.LastRaidKills), 0, 100);
            dossier.Stress = Clamp(dossier.Stress + Math.Min(8, dossier.LastRaidKills * 2) - 6, 0, 100);
            dossier.Fatigue = Clamp(dossier.Fatigue + 8 + Math.Min(10, dossier.LastRaidItemsExtracted), 0, 100);
            return;
        }

        dossier.SurvivalStreak = 0;
        dossier.Trust = Clamp(dossier.Trust - 5, 0, 100);
        dossier.Stress = Clamp(dossier.Stress + 25, 0, 100);
        dossier.Fatigue = Clamp(dossier.Fatigue + 15, 0, 100);
    }

    private static string BuildDossierSummary(ScavLifeProfileState profile, string condition)
    {
        var dossier = profile.Dossier;
        return $"{profile.ActiveScav.Nickname} is {condition}; streak {dossier.SurvivalStreak}, trust {dossier.Trust}, stress {dossier.Stress}, fatigue {dossier.Fatigue}.";
    }

    private static List<string> BuildObjectives(ScavLifeProfileState profile, ScavLifeKitPreferences kit, string suggestedMap)
    {
        var objectives = new List<string>
        {
            $"Deploy to {suggestedMap} and prioritize {kit.LootFocus}.",
            "Extract once the pack has meaningful value; survival is the main progression path."
        };

        if (profile.Dossier.SurvivalStreak >= 3)
        {
            objectives.Add("Protect the current survival streak; skip optional fights.");
        }

        if (profile.Dossier.Trust >= 40)
        {
            objectives.Add("Take one calculated risk for higher-value loot if extraction remains clear.");
        }

        if (profile.Dossier.Stress >= 60 || profile.Dossier.Fatigue >= 60)
        {
            objectives.Add("Run short and leave early to recover condition.");
        }

        return objectives;
    }

    private static List<string> BuildAvoidList(ScavLifeProfileState profile, ScavLifeKitPreferences kit)
    {
        var avoid = new List<string>
        {
            "Avoid boss routes and prolonged gunfights unless extraction is blocked."
        };

        if (kit.Armor is "none" or "light")
        {
            avoid.Add("Avoid open lanes and armor-check fights.");
        }

        if (profile.Dossier.Stress >= 50)
        {
            avoid.Add("Avoid chasing shots; reposition after contact.");
        }

        if (profile.Dossier.Fatigue >= 50)
        {
            avoid.Add("Avoid heavy loot detours that delay extraction.");
        }

        return avoid;
    }

    private static string GetCondition(ScavLifeProfileState profile, long now)
    {
        if (!profile.ActiveScav.Alive)
        {
            return profile.ActiveScav.ReadyAtUnixTime <= now ? "replacement-ready" : "missing";
        }

        if (profile.ActiveScav.ReadyAtUnixTime > now)
        {
            return "recovering";
        }

        if (profile.Dossier.Stress >= 70 || profile.Dossier.Fatigue >= 70)
        {
            return "strained";
        }

        if (profile.Dossier.SurvivalStreak >= 3)
        {
            return "seasoned";
        }

        return "ready";
    }

    private static string GetRiskLevel(int riskScore)
    {
        if (riskScore >= 90)
        {
            return "extreme";
        }

        if (riskScore >= 60)
        {
            return "high";
        }

        if (riskScore >= 30)
        {
            return "medium";
        }

        return "low";
    }

    private static string GetExtractionStyle(string temperament, ScavLifeDossier dossier)
    {
        if (dossier.Stress >= 70 || dossier.Fatigue >= 70)
        {
            return "short raid, first clean extract";
        }

        return temperament switch
        {
            "opportunist" => "loot fast, leave when value appears",
            "evasive" => "avoid contact and chain cover",
            "stubborn" => "hold route, but break contact after damage",
            "desperate" => "grab essentials and leave",
            "loyal" => "stick to familiar extracts and avoid betrayal penalties",
            _ => "cautious loot route with early extract option"
        };
    }

    private static string GetBudgetTier(ScavLifeProfileState profile)
    {
        if (profile.Dossier.Trust >= 70 || profile.ActiveScav.Level >= 15)
        {
            return "trusted";
        }

        if (profile.Dossier.Trust >= 35 || profile.ActiveScav.Level >= 7)
        {
            return "standard";
        }

        return "barebones";
    }

    private void SaveState()
    {
        var json = JsonSerializer.Serialize(_state, JsonOptions);
        File.WriteAllText(StatePath, json);
    }

    private static T LoadOrCreate<T>(string path, T fallback)
    {
        if (!File.Exists(path))
        {
            File.WriteAllText(path, JsonSerializer.Serialize(fallback, JsonOptions));
            return fallback;
        }

        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<T>(json, JsonOptions) ?? fallback;
    }

    private static long Now()
    {
        return DateTimeOffset.UtcNow.ToUnixTimeSeconds();
    }

    private static long MinutesToSeconds(int minutes)
    {
        return Math.Max(0, minutes) * 60L;
    }

    private static int CalculateLevel(int experience)
    {
        return Math.Max(1, (experience / 1000) + 1);
    }

    private static ScavLifeCustomization CreateDefaultCustomization(string? nickname)
    {
        var displayName = string.IsNullOrWhiteSpace(nickname) ? "Local" : nickname.Trim();
        return new ScavLifeCustomization
        {
            DisplayName = displayName,
            Archetype = "local",
            HomeMap = "tarkovstreets",
            Temperament = "cautious",
            Voice = "quiet",
            OutfitPreset = "scrapper",
            Tags = ["local", "persistent"],
            KitPreferences = new ScavLifeKitPreferences()
        };
    }

    private bool EnsureProfileShape(ScavLifeProfileState profile)
    {
        var changed = false;

        if (profile.ActiveScav is null)
        {
            profile.ActiveScav = CreateScav(profile.ProfileId, Math.Max(1, profile.Generation), _config.StartingScav.Nickname);
            changed = true;
        }

        if (profile.ActiveScav.Customization is null)
        {
            profile.ActiveScav.Customization = CreateDefaultCustomization(profile.ActiveScav.Nickname);
            changed = true;
        }

        if (string.IsNullOrWhiteSpace(profile.ActiveScav.Customization.DisplayName))
        {
            profile.ActiveScav.Customization.DisplayName = profile.ActiveScav.Nickname;
            changed = true;
        }

        if (profile.ActiveScav.Customization.KitPreferences is null)
        {
            profile.ActiveScav.Customization.KitPreferences = new ScavLifeKitPreferences();
            changed = true;
        }

        if (profile.Stash is null)
        {
            profile.Stash = new ScavLifeStash();
            changed = true;
        }

        if (profile.PendingHauls is null)
        {
            profile.PendingHauls = [];
            changed = true;
        }

        if (profile.Dossier is null)
        {
            profile.Dossier = new ScavLifeDossier();
            changed = true;
        }

        if (profile.Stash.Width <= 0)
        {
            profile.Stash.Width = _config.Stash.Width;
            changed = true;
        }

        if (profile.Stash.Height <= 0)
        {
            profile.Stash.Height = _config.Stash.Height;
            changed = true;
        }

        profile.Stash.Items ??= [];
        foreach (var item in profile.Stash.Items)
        {
            changed |= EnsureStashItemShape(item, "stored");
        }

        foreach (var haul in profile.PendingHauls)
        {
            haul.Items ??= [];
            haul.Decisions ??= [];
            foreach (var item in haul.Items)
            {
                changed |= EnsureStashItemShape(item, "pending");
                if (string.IsNullOrWhiteSpace(item.SourceHaulId))
                {
                    item.SourceHaulId = haul.Id;
                    changed = true;
                }
            }

            var previousItemTreeCount = haul.ItemTreeCount;
            var previousFlatItemCount = haul.FlatItemCount;
            RefreshHaulCounts(haul);
            changed |= previousItemTreeCount != haul.ItemTreeCount || previousFlatItemCount != haul.FlatItemCount;
            if (string.IsNullOrWhiteSpace(haul.Status))
            {
                haul.Status = haul.Items.Count > 0 ? "pending" : "allocated";
                changed = true;
            }
        }

        profile.ActiveScav.Customization.Tags ??= [];
        profile.Dossier.Trust = Clamp(profile.Dossier.Trust, 0, 100);
        profile.Dossier.Stress = Clamp(profile.Dossier.Stress, 0, 100);
        profile.Dossier.Fatigue = Clamp(profile.Dossier.Fatigue, 0, 100);
        profile.Dossier.LastCaptureSource = string.IsNullOrWhiteSpace(profile.Dossier.LastCaptureSource)
            ? "none"
            : profile.Dossier.LastCaptureSource;
        profile.Dossier.LastCaptureKey ??= "";

        return changed;
    }

    private static bool EnsureStashItemShape(ScavLifeStashItem item, string defaultStatus)
    {
        var changed = false;
        if (string.IsNullOrWhiteSpace(item.Id))
        {
            item.Id = NewLedgerId(defaultStatus == "pending" ? "pending" : "stash");
            changed = true;
        }

        if (string.IsNullOrWhiteSpace(item.Status))
        {
            item.Status = defaultStatus;
            changed = true;
        }

        if (string.IsNullOrWhiteSpace(item.Source))
        {
            item.Source = "framework";
            changed = true;
        }

        if (item.StackCount <= 0)
        {
            item.StackCount = 1;
            changed = true;
        }

        if (item.ItemCount <= 0)
        {
            item.ItemCount = Math.Max(1, item.ItemTree?.Count ?? 1);
            changed = true;
        }

        item.ItemTree ??= [];
        item.TemplateId ??= "";
        item.SourceHaulId ??= "";
        item.OriginalRootItemId ??= "";
        item.RootParentId ??= "";
        item.RootSlotId ??= "";
        return changed;
    }

    private static bool ApplyCustomizationRequest(ScavLifeScav scav, ScavLifeCustomizeRequest request)
    {
        var changed = false;
        var customization = scav.Customization ??= CreateDefaultCustomization(scav.Nickname);

        if (!string.IsNullOrWhiteSpace(request.Nickname))
        {
            var nickname = SanitizeText(request.Nickname, 24);
            changed |= SetStringIfChanged(value => scav.Nickname = value, scav.Nickname, nickname);
            changed |= SetStringIfChanged(value => customization.DisplayName = value, customization.DisplayName, nickname);
        }

        changed |= SetAllowedIfProvided(value => customization.Archetype = value, customization.Archetype, request.Archetype, Archetypes);
        changed |= SetAllowedIfProvided(value => customization.HomeMap = value, customization.HomeMap, request.HomeMap, HomeMaps);
        changed |= SetAllowedIfProvided(value => customization.Temperament = value, customization.Temperament, request.Temperament, Temperaments);
        changed |= SetAllowedIfProvided(value => customization.Voice = value, customization.Voice, request.Voice, Voices);
        changed |= SetAllowedIfProvided(value => customization.OutfitPreset = value, customization.OutfitPreset, request.OutfitPreset, OutfitPresets);

        if (request.Tags is not null)
        {
            var tags = request.Tags
                .Select(tag => SanitizeText(tag, 24))
                .Where(tag => tag.Length > 0)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Take(8)
                .ToList();

            if (!customization.Tags.SequenceEqual(tags, StringComparer.OrdinalIgnoreCase))
            {
                customization.Tags = tags;
                changed = true;
            }
        }

        if (request.KitPreferences is not null)
        {
            customization.KitPreferences ??= new ScavLifeKitPreferences();
            changed |= SetAllowedIfProvided(value => customization.KitPreferences.PrimaryWeapon = value, customization.KitPreferences.PrimaryWeapon, request.KitPreferences.PrimaryWeapon, PrimaryWeaponPreferences);
            changed |= SetAllowedIfProvided(value => customization.KitPreferences.Armor = value, customization.KitPreferences.Armor, request.KitPreferences.Armor, ArmorPreferences);
            changed |= SetAllowedIfProvided(value => customization.KitPreferences.Backpack = value, customization.KitPreferences.Backpack, request.KitPreferences.Backpack, BackpackPreferences);
            changed |= SetAllowedIfProvided(value => customization.KitPreferences.Medical = value, customization.KitPreferences.Medical, request.KitPreferences.Medical, MedicalPreferences);
            changed |= SetAllowedIfProvided(value => customization.KitPreferences.LootFocus = value, customization.KitPreferences.LootFocus, request.KitPreferences.LootFocus, LootFocusPreferences);
        }

        return changed;
    }

    private static bool SetAllowedIfProvided(Action<string> setter, string current, string? requested, IEnumerable<string> allowedValues)
    {
        if (string.IsNullOrWhiteSpace(requested))
        {
            return false;
        }

        var value = GetAllowedValue(requested, allowedValues);
        return SetStringIfChanged(setter, current, value);
    }

    private static string GetAllowedValue(string requested, IEnumerable<string> allowedValues)
    {
        var normalizedRequested = Normalize(requested);
        return allowedValues.FirstOrDefault(value => Normalize(value) == normalizedRequested)
            ?? allowedValues.First();
    }

    private static bool SetStringIfChanged(Action<string> setter, string current, string requested)
    {
        if (string.Equals(current, requested, StringComparison.Ordinal))
        {
            return false;
        }

        setter(requested);
        return true;
    }

    private static string Pick(IEnumerable<string> values)
    {
        var list = values as string[] ?? values.ToArray();
        return list[Random.Shared.Next(list.Length)];
    }

    private static string SanitizeText(string? value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var cleaned = new string(value
            .Trim()
            .Where(character => !char.IsControl(character))
            .ToArray());

        return cleaned.Length <= maxLength ? cleaned : cleaned[..maxLength];
    }

    private static string Truncate(string? value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        if (maxLength <= 0 || value.Length <= maxLength)
        {
            return value;
        }

        return value[..maxLength] + "...";
    }

    private static bool IsScavSide(string? side)
    {
        return side?.Contains("scav", StringComparison.OrdinalIgnoreCase) == true
            || side?.Contains("savage", StringComparison.OrdinalIgnoreCase) == true;
    }

    private static string CleanLocation(string? location)
    {
        return string.IsNullOrWhiteSpace(location) ? "unknown" : location.Trim();
    }

    private static string NormalizeDestination(string? destination)
    {
        return Normalize(destination) switch
        {
            "scavstash" or "scavlifestash" or "scavlife" => "scav-stash",
            "pmcstash" or "mainstash" or "vanillastash" => "pmc-stash",
            "fence" or "sell" or "selltofence" => "fence",
            _ => ""
        };
    }

    private static string SafeFileToken(string? value)
    {
        var cleaned = new string((value ?? "")
            .Where(character => char.IsLetterOrDigit(character) || character is '-' or '_')
            .ToArray());

        return string.IsNullOrWhiteSpace(cleaned) ? "unknown" : cleaned;
    }

    private static string NewLedgerId(string prefix)
    {
        return $"{prefix}-{Guid.NewGuid():N}";
    }

    private static string FirstNonBlank(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Trim();
            }
        }

        return "unknown";
    }

    private static string? ReadExtensionString(Dictionary<string, object>? extensionData, string key)
    {
        if (extensionData is null || !extensionData.TryGetValue(key, out var value) || value is null)
        {
            return null;
        }

        return value switch
        {
            string text => text,
            JsonElement element when element.ValueKind == JsonValueKind.String => element.GetString(),
            _ => value.ToString()
        };
    }

    private static string Normalize(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        return new string(value
            .Where(char.IsLetterOrDigit)
            .Select(char.ToLowerInvariant)
            .ToArray());
    }

    private static int Clamp(int value, int min, int max)
    {
        return Math.Min(max, Math.Max(min, value));
    }

    private sealed class ScavLifeRaidContext
    {
        public string Location { get; set; } = "unknown";
        public string ServerId { get; set; } = "";
        public string PlayerSide { get; set; } = "";
        public long StartedAtUnixTime { get; set; }
    }

    private sealed record ScavLifePostRaidCapture(
        string CaptureKey,
        ScavLifeCompleteRunRequest Request,
        ScavLifeSurvivalAssessment Assessment);

    private sealed class ScavLifeSurvivalAssessment
    {
        public bool? Survived { get; set; }
        public string Reason { get; set; } = "";
        public List<string> ExitStatuses { get; set; } = [];
        public double Deaths { get; set; }
        public double ExitExperience { get; set; }
        public double TotalSessionExperience { get; set; }
        public bool HasMeaningfulDeathCause { get; set; }
        public string DeathCauseSummary { get; set; } = "";
        public int FoundInRaidItemCount { get; set; }
        public int InventoryItemCount { get; set; }
        public int ExtractedRootItemCount { get; set; }
    }
}
