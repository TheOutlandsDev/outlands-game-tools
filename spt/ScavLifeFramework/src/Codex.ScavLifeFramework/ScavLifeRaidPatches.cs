using SPTarkov.Reflection.Patching;
using SPTarkov.Server.Core.Controllers;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.InRaid;
using SPTarkov.Server.Core.Models.Eft.Match;
using System.Reflection;

namespace Codex.ScavLifeFramework;

internal sealed class ScavLifeRaidStartPatch : AbstractPatch
{
    private static Action<MongoId, StartLocalRaidRequestData?>? recordRaidStart;

    public ScavLifeRaidStartPatch() : base("codex.scavlife.raid-start")
    {
    }

    public static void Configure(Action<MongoId, StartLocalRaidRequestData?> recordAction)
    {
        recordRaidStart = recordAction;
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(MatchController).GetMethod(
            nameof(MatchController.StartLocalRaid),
            BindingFlags.Instance | BindingFlags.Public)!;
    }

    [PatchPostfix]
    public static void PatchPostfix(MongoId sessionId, StartLocalRaidRequestData request)
    {
        recordRaidStart?.Invoke(sessionId, request);
    }
}

internal sealed class ScavLifePostRaidScavSavePatch : AbstractPatch
{
    private static Action<MongoId, ScavSaveRequestData?>? capturePostRaidScav;

    public ScavLifePostRaidScavSavePatch() : base("codex.scavlife.post-raid-scav-save")
    {
    }

    public static void Configure(Action<MongoId, ScavSaveRequestData?> captureAction)
    {
        capturePostRaidScav = captureAction;
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(InRaidController).GetMethod(
            nameof(InRaidController.SavePostRaidProfileForScav),
            BindingFlags.Instance | BindingFlags.Public)!;
    }

    [PatchPostfix]
    public static void PatchPostfix(ScavSaveRequestData offRaidProfileData, MongoId sessionId)
    {
        capturePostRaidScav?.Invoke(sessionId, offRaidProfileData);
    }
}
