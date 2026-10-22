using SPTarkov.DI.Annotations;
using SPTarkov.Server.Core.DI;
using SPTarkov.Server.Core.Models.Common;
using SPTarkov.Server.Core.Models.Eft.Common;
using SPTarkov.Server.Core.Models.Enums;
using SPTarkov.Server.Core.Utils;

namespace Codex.ScavLifeFramework;

[Injectable]
public sealed class ScavLifeStaticRouter : StaticRouter
{
    public ScavLifeStaticRouter(
        JsonUtil jsonUtil,
        ScavLifeService scavLifeService,
        HttpResponseUtil httpResponseUtil)
        : base(jsonUtil, BuildRoutes(scavLifeService, httpResponseUtil))
    {
    }

    private static IEnumerable<RouteAction> BuildRoutes(
        ScavLifeService scavLifeService,
        HttpResponseUtil httpResponseUtil)
    {
        return
        [
            new RouteAction<EmptyRequestData>(
                "/singleplayer/scavlife/ping",
                (_, _, sessionId, _) => Body(httpResponseUtil, scavLifeService.GetStatus(ScavLifeService.ResolveProfileId(sessionId, null)))),

            new RouteAction<ScavLifeProfileRequest>(
                "/singleplayer/scavlife/status",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.GetStatus(Resolve(sessionId, request.ProfileId)))),

            new RouteAction<ScavLifeProfileRequest>(
                "/singleplayer/scavlife/dossier",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.GetDossier(Resolve(sessionId, request.ProfileId)))),

            new RouteAction<ScavLifeRaidPlanRequest>(
                "/singleplayer/scavlife/raid-plan",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.GetRaidPlan(Resolve(sessionId, request.ProfileId), request.Location))),

            new RouteAction<ScavLifeProfileRequest>(
                "/singleplayer/scavlife/stash/status",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.GetStashStatus(Resolve(sessionId, request.ProfileId)))),

            new RouteAction<ScavLifeStashDecisionRequest>(
                "/singleplayer/scavlife/stash/decision",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.DecidePendingHaul(Resolve(sessionId, request.ProfileId), request))),

            new RouteAction<ScavLifeSeedRequest>(
                "/singleplayer/scavlife/debug/seed",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.Seed(Resolve(sessionId, request.ProfileId), request.Nickname, request.Force))),

            new RouteAction<ScavLifeCompleteRunRequest>(
                "/singleplayer/scavlife/debug/complete-run",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.CompleteRun(Resolve(sessionId, request.ProfileId), request))),

            new RouteAction<ScavLifeProfileRequest>(
                "/singleplayer/scavlife/customization/options",
                (_, _, _, _) => Body(httpResponseUtil, scavLifeService.GetCustomizationOptions())),

            new RouteAction<ScavLifeCustomizeRequest>(
                "/singleplayer/scavlife/customization/apply",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.Customize(Resolve(sessionId, request.ProfileId), request))),

            new RouteAction<ScavLifeRandomizeCustomizationRequest>(
                "/singleplayer/scavlife/customization/randomize",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.RandomizeCustomization(Resolve(sessionId, request.ProfileId), request))),

            new RouteAction<ScavLifeResetRequest>(
                "/singleplayer/scavlife/debug/reset",
                (_, request, sessionId, _) => Body(httpResponseUtil, scavLifeService.Reset(Resolve(sessionId, request.ProfileId))))
        ];
    }

    private static string Resolve(MongoId sessionId, string? profileId)
    {
        return ScavLifeService.ResolveProfileId(sessionId, profileId);
    }

    private static ValueTask<string> Body<T>(HttpResponseUtil httpResponseUtil, T data)
    {
        return new ValueTask<string>(httpResponseUtil.GetBody(data, BackendErrorCodes.None, "", true));
    }
}
