using SPTarkov.Reflection.Patching;
using SPTarkov.Server.Core.Helpers;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common;
using System.Reflection;

namespace Codex.ScavLifeFramework;

internal sealed class ScavLifeProfileSyncPatch : AbstractPatch
{
    private static Action<MongoId, PmcData?>? sync;

    public ScavLifeProfileSyncPatch() : base("codex.scavlife.profile-sync")
    {
    }

    public static void Configure(Action<MongoId, PmcData?> syncAction)
    {
        sync = syncAction;
    }

    protected override MethodBase GetTargetMethod()
    {
        return typeof(ProfileHelper).GetMethod(
            nameof(ProfileHelper.GetScavProfile),
            BindingFlags.Instance | BindingFlags.Public,
            [typeof(MongoId)])!;
    }

    [PatchPostfix]
    public static void PatchPostfix(MongoId sessionId, PmcData? __result)
    {
        sync?.Invoke(sessionId, __result);
    }
}
