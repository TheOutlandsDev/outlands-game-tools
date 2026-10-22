using SPTarkov.DI.Annotations;
using SPTarkov.Reflection.Patching;
using SPTarkov.Server.Core.Models.External;
using SPTarkov.Server.Core.Services;
using SPTarkov.Server.Core.Utils.Logger;
using System.Reflection;

namespace Codex.OpenScavTransits;

[Injectable]
public sealed class OpenScavTransitsMod(
    OpenScavTransitsService openScavTransitsService,
    TraderAvailabilityService traderAvailabilityService,
    SptLogger<OpenScavTransitsMod> logger) : IOnWebAppBuildModAsync
{
    public Task OnWebAppBuildAsync()
    {
        OpenScavTransitsPostDbPatch.Configure(openScavTransitsService.Apply);
        new OpenScavTransitsPostDbPatch().Enable();

        traderAvailabilityService.Initialize();
        TraderAvailabilityGetAllTradersPatch.Configure(traderAvailabilityService.FilterTraders);
        TraderAvailabilityStartLocalRaidPatch.Configure(traderAvailabilityService.RecordStartLocalRaid);
        TraderAvailabilityEndLocalRaidPatch.Configure(traderAvailabilityService.RecordEndLocalRaid);
        new TraderAvailabilityGetAllTradersPatch().Enable();
        new TraderAvailabilityStartLocalRaidPatch().Enable();
        new TraderAvailabilityEndLocalRaidPatch().Enable();

        logger.Info("Codex Open Scav Transits installed map, transit, and trader availability patches.", null);
        return Task.CompletedTask;
    }
}

internal sealed class OpenScavTransitsPostDbPatch : AbstractPatch
{
    private static Action? apply;

    public OpenScavTransitsPostDbPatch() : base("codex.open-scav-transits.post-db")
    {
    }

    public static void Configure(Action applyAction)
    {
        apply = applyAction;
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(PostDbLoadService).GetMethod(
            nameof(PostDbLoadService.PerformPostDbLoadActions),
            BindingFlags.Instance | BindingFlags.Public)!;
    }

    [PatchPostfix]
    public static void PatchPostfix()
    {
        apply?.Invoke();
    }
}
