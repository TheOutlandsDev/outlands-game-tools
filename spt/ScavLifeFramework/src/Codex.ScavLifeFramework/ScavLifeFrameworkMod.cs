using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.Models.External;
using SPTarkov.Server.Core.Utils.Logger;

namespace Codex.ScavLifeFramework;

[Injectable]
public sealed class ScavLifeFrameworkMod(
    ScavLifeService scavLifeService,
    SptLogger<ScavLifeFrameworkMod> logger) : IOnWebAppBuildModAsync
{
    public Task OnWebAppBuildAsync()
    {
        scavLifeService.Initialize();
        ScavLifeRaidStartPatch.Configure(scavLifeService.RecordRaidStart);
        ScavLifePostRaidScavSavePatch.Configure(scavLifeService.CapturePostRaidScav);
        new ScavLifeRaidStartPatch().Enable();
        new ScavLifePostRaidScavSavePatch().Enable();
        logger.Success("Scav Life Framework 0.5.1 ready. Post-raid scav haul capture and audit logging are active under /singleplayer/scavlife/*.", null);
        return Task.CompletedTask;
    }
}
