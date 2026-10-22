using SPTarkov.Reflection.Patching;
using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.External;
using SPTarkov.Server.Core.Services;
using SPTarkov.Server.Core.Utils.Logger;
using System.Reflection;

namespace Codex.FpvDroneParentCachePreload;

[Injectable]
public sealed class FpvDroneParentCachePreload(
    SptLogger<FpvDroneParentCachePreload> logger) : IOnWebAppBuildModAsync
{
    private const string DroneParentId = "6964ea3a5e4c1218314e1b2f";
    private const string PayloadParentId = "69669ea64847b58fd5393f71";

    public Task OnWebAppBuildAsync()
    {
        new FpvParentEnumerableBaseClassPatch().Enable();
        new FpvParentSingleBaseClassPatch().Enable();
        logger.Success("Installed FPV Drone custom parent base-class compatibility patches.", null);
        return Task.CompletedTask;
    }

    internal static bool IsFpvParent(MongoId itemTpl)
    {
        var value = itemTpl.ToString();
        return value == DroneParentId || value == PayloadParentId;
    }
}

internal sealed class FpvParentEnumerableBaseClassPatch : AbstractPatch
{
    public FpvParentEnumerableBaseClassPatch() : base("codex.fpvdronemod.parentcachepreload.enumerable")
    {
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(ItemBaseClassService).GetMethod(
            nameof(ItemBaseClassService.ItemHasBaseClass),
            [typeof(MongoId), typeof(IEnumerable<MongoId>)])!;
    }

    [PatchPrefix]
    public static bool PatchPrefix(MongoId itemTpl, ref bool __result)
    {
        if (!FpvDroneParentCachePreload.IsFpvParent(itemTpl))
        {
            return true;
        }

        __result = false;
        return false;
    }
}

internal sealed class FpvParentSingleBaseClassPatch : AbstractPatch
{
    public FpvParentSingleBaseClassPatch() : base("codex.fpvdronemod.parentcachepreload.single")
    {
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(ItemBaseClassService).GetMethod(
            nameof(ItemBaseClassService.ItemHasBaseClass),
            [typeof(MongoId), typeof(MongoId)])!;
    }

    [PatchPrefix]
    public static bool PatchPrefix(MongoId itemTpl, ref bool __result)
    {
        if (!FpvDroneParentCachePreload.IsFpvParent(itemTpl))
        {
            return true;
        }

        __result = false;
        return false;
    }
}
