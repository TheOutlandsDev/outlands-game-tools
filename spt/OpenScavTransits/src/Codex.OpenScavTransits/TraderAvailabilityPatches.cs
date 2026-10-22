using SPTarkov.Reflection.Patching;
using SPTarkov.Server.Core.Controllers;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common.Tables;
using SPTarkov.Server.Core.Models.Eft.Match;
using System.Reflection;

namespace Codex.OpenScavTransits;

internal sealed class TraderAvailabilityGetAllTradersPatch : AbstractPatch
{
    private static Func<MongoId, List<TraderBase>, List<TraderBase>>? filter;

    public TraderAvailabilityGetAllTradersPatch() : base("codex.trader-availability.get-all-traders")
    {
    }

    public static void Configure(Func<MongoId, List<TraderBase>, List<TraderBase>> filterAction)
    {
        filter = filterAction;
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(TraderController).GetMethod(
            nameof(TraderController.GetAllTraders),
            BindingFlags.Instance | BindingFlags.Public)!;
    }

    [PatchPostfix]
    public static void PatchPostfix(MongoId sessionId, ref List<TraderBase> __result)
    {
        if (filter is null || __result is null)
        {
            return;
        }

        __result = filter(sessionId, __result);
    }
}

internal sealed class TraderAvailabilityStartLocalRaidPatch : AbstractPatch
{
    private static Action<StartLocalRaidRequestData>? recordStartLocalRaid;

    public TraderAvailabilityStartLocalRaidPatch() : base("codex.trader-availability.start-local-raid")
    {
    }

    public static void Configure(Action<StartLocalRaidRequestData> recordAction)
    {
        recordStartLocalRaid = recordAction;
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(MatchController).GetMethod(
            nameof(MatchController.StartLocalRaid),
            BindingFlags.Instance | BindingFlags.Public)!;
    }

    [PatchPostfix]
    public static void PatchPostfix(StartLocalRaidRequestData request)
    {
        recordStartLocalRaid?.Invoke(request);
    }
}

internal sealed class TraderAvailabilityEndLocalRaidPatch : AbstractPatch
{
    private static Action<EndLocalRaidRequestData>? recordEndLocalRaid;

    public TraderAvailabilityEndLocalRaidPatch() : base("codex.trader-availability.end-local-raid")
    {
    }

    public static void Configure(Action<EndLocalRaidRequestData> recordAction)
    {
        recordEndLocalRaid = recordAction;
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(MatchController).GetMethod(
            nameof(MatchController.EndLocalRaid),
            BindingFlags.Instance | BindingFlags.Public)!;
    }

    [PatchPostfix]
    public static void PatchPostfix(EndLocalRaidRequestData request)
    {
        recordEndLocalRaid?.Invoke(request);
    }
}
