using SPTarkov.DI.Annotations;
using SPTarkov.Reflection.Patching;
using SPTarkov.Server.Core.Models.External;
using SPTarkov.Server.Core.Services;
using SPTarkov.Server.Core.Utils.Logger;
using System.Reflection;

namespace Codex.AiPopulationTuning;

[Injectable]
public sealed class AiPopulationTuningMod(
    AiPopulationTuningService tuningService,
    SptLogger<AiPopulationTuningMod> logger) : IOnWebAppBuildModAsync
{
    public Task OnWebAppBuildAsync()
    {
        AiPopulationTuningPostDbPatch.Configure(tuningService.Apply);
        new AiPopulationTuningPostDbPatch().Enable();

        logger.Info("Codex AI Population Tuning installed post-database patch.", null);
        return Task.CompletedTask;
    }
}

internal sealed class AiPopulationTuningPostDbPatch : AbstractPatch
{
    private static Action? apply;

    public AiPopulationTuningPostDbPatch() : base("codex.ai-population-tuning.post-db")
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
