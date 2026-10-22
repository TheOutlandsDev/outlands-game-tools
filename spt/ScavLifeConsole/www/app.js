const state = {
  profileId: "local-test",
  apiToken: "",
  mutationsEnabled: false,
  options: null,
  status: null,
  dossier: null,
  raidPlan: null,
  dashboard: null
};

const fallbackOptions = {
  archetypes: ["local", "scrounger", "courier", "lookout", "medic", "fixer", "bruiser", "survivor"],
  homeMaps: ["tarkovstreets", "sandbox", "sandbox_high", "factory4_day", "woods", "bigmap", "interchange", "shoreline", "lighthouse", "rezervbase"],
  temperaments: ["cautious", "opportunist", "evasive", "stubborn", "loyal", "desperate"],
  voices: ["quiet", "nervous", "mumbling", "swagger", "angry"],
  outfitPresets: ["scrapper", "worker", "hooded", "ex-security", "field-medic"],
  kitPreferences: {
    primaryWeapons: ["whatever-runs", "shotgun", "smg", "rifle", "marksman", "pistol"],
    armor: ["none", "light", "balanced", "helmet-first"],
    backpacks: ["pockets-only", "small-pack", "large-pack"],
    medical: ["cheap-bandages", "balanced", "painkiller-first"],
    lootFocus: ["food", "medicine", "hardware", "weapons", "valuables"]
  }
};

const $ = (id) => document.getElementById(id);

function pick(object, ...keys) {
  if (!object) return undefined;
  for (const key of keys) {
    if (object[key] !== undefined && object[key] !== null) return object[key];
  }
  return undefined;
}

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return undefined;
}

function unwrap(proxyResponse) {
  const payload = proxyResponse?.data ?? proxyResponse;
  if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "data")) {
    return payload.data;
  }
  return payload;
}

function setText(id, value) {
  $(id).textContent = value === undefined || value === null || value === "" ? "-" : String(value);
}

function setLog(message, kind = "muted") {
  const log = $("eventLog");
  log.textContent = message;
  log.dataset.kind = kind;
}

function setPill(id, text, mode = "muted") {
  const pill = $(id);
  pill.textContent = text;
  pill.className = `status-pill ${mode}`;
}

async function request(path, body = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json", "X-ScavLife-Token": state.apiToken },
    body: JSON.stringify({ profileId: currentProfileId(), ...body })
  });
  const result = await response.json();
  if (!response.ok || result.ok === false) {
    throw new Error(result.error || `Request failed: ${path}`);
  }
  return unwrap(result);
}

async function loadConfig() {
  const response = await fetch("/api/config");
  const config = await response.json();
  if (!response.ok || config.ok === false) {
    throw new Error(config.error || "Could not load console config.");
  }
  state.profileId = config.profileId || "local-test";
  state.apiToken = config.apiToken || "";
  state.mutationsEnabled = config.mutationsEnabled === true;
  for (const id of ["applyButton", "randomizeButton", "resetButton"]) {
    $(id).disabled = !state.mutationsEnabled;
    $(id).title = state.mutationsEnabled ? "" : "State changes require -EnableMutations when starting the console.";
  }
  $("profileInput").value = state.profileId;
  $("serverLine").textContent = `${config.listenPrefix} -> ${config.sptBaseUrl}`;
}

function currentProfileId() {
  return $("profileInput").value.trim() || state.profileId || "local-test";
}

function fillSelect(select, values, selectedValue) {
  select.innerHTML = "";
  for (const value of values || []) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  }
  if (selectedValue && [...select.options].some((option) => option.value === selectedValue)) {
    select.value = selectedValue;
  }
}

function fillLists(list, values) {
  list.innerHTML = "";
  for (const value of values || []) {
    const item = document.createElement("li");
    item.textContent = value;
    list.appendChild(item);
  }
}

function fillSignals(list, values) {
  list.innerHTML = "";
  const signals = values || [];
  if (signals.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No recent warning or error signals.";
    list.appendChild(item);
    return;
  }

  for (const value of signals) {
    const item = document.createElement("li");
    item.textContent = value;
    list.appendChild(item);
  }
}

function fillChips(container, values, className = "data-chip") {
  container.innerHTML = "";
  for (const value of values || []) {
    const chip = document.createElement("span");
    chip.className = `${className} ${value.mode || ""}`.trim();
    chip.textContent = value.text || "-";
    container.appendChild(chip);
  }
}

function fillIssues(list, issues) {
  list.innerHTML = "";
  const items = issues || [];
  if (items.length === 0) {
    const item = document.createElement("li");
    item.dataset.severity = "ok";
    const title = document.createElement("div");
    title.className = "issue-title";
    title.textContent = "No active dashboard issues.";
    item.appendChild(title);
    list.appendChild(item);
    return;
  }

  for (const issue of items) {
    const item = document.createElement("li");
    item.dataset.severity = pick(issue, "severity", "Severity") || "info";
    const title = document.createElement("div");
    title.className = "issue-title";
    title.textContent = `${pick(issue, "source", "Source") || "System"}: ${pick(issue, "title", "Title") || "Issue"}`;
    const detail = document.createElement("div");
    detail.className = "issue-detail";
    detail.textContent = pick(issue, "detail", "Detail") || "";
    item.append(title, detail);
    list.appendChild(item);
  }
}

function fillTable(tbody, rows, columns, emptyText = "No data.") {
  tbody.innerHTML = "";
  const items = rows || [];
  if (items.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns.length;
    td.textContent = emptyText;
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  for (const row of items) {
    const tr = document.createElement("tr");
    for (const column of columns) {
      const td = document.createElement("td");
      const value = typeof column.value === "function" ? column.value(row) : pick(row, column.value, pascal(column.value));
      td.textContent = value === undefined || value === null || value === "" ? "-" : String(value);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
}

function pascal(value) {
  return value ? `${value[0].toUpperCase()}${value.slice(1)}` : value;
}

function formatUnixTime(value) {
  const seconds = Number(value || 0);
  if (!Number.isFinite(seconds) || seconds <= 0) return "-";
  return new Date(seconds * 1000).toLocaleString();
}

function formatBoolean(value) {
  return value ? "on" : "off";
}

function formatMs(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number.toFixed(number >= 100 ? 0 : 1)} ms`;
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return number.toLocaleString();
}

function severityMode(severity) {
  if (severity === "error") return "bad";
  if (severity === "warn") return "warn";
  if (severity === "ok") return "ok";
  return "muted";
}

function buildLocalScavSummary(localScavLife) {
  if (!localScavLife || Object.keys(localScavLife).length === 0) return "";
  const name = pick(localScavLife, "nickname", "Nickname") || "Scav";
  const streak = pick(localScavLife, "survivalStreak", "SurvivalStreak") || 0;
  const trust = pick(localScavLife, "trust", "Trust") || 0;
  const stress = pick(localScavLife, "stress", "Stress") || 0;
  const fatigue = pick(localScavLife, "fatigue", "Fatigue") || 0;
  return `${name} local state; streak ${streak}, trust ${trust}, stress ${stress}, fatigue ${fatigue}.`;
}

async function loadOptions() {
  state.options = await request("/api/scavlife/customization/options");
  applyOptions(state.options);
}

function applyOptions(options) {
  state.options = options;
  const kit = pick(state.options, "kitPreferences", "KitPreferences") || {};
  const maps = pick(state.options, "homeMaps", "HomeMaps") || [];

  fillSelect($("mapSelect"), maps, $("mapSelect").value || "tarkovstreets");
  fillSelect($("homeMapSelect"), maps);
  fillSelect($("archetypeSelect"), pick(state.options, "archetypes", "Archetypes"));
  fillSelect($("temperamentSelect"), pick(state.options, "temperaments", "Temperaments"));
  fillSelect($("voiceSelect"), pick(state.options, "voices", "Voices"));
  fillSelect($("outfitSelect"), pick(state.options, "outfitPresets", "OutfitPresets"));
  fillSelect($("primarySelect"), pick(kit, "primaryWeapons", "PrimaryWeapons"));
  fillSelect($("armorSelect"), pick(kit, "armor", "Armor"));
  fillSelect($("backpackSelect"), pick(kit, "backpacks", "Backpacks"));
  fillSelect($("medicalSelect"), pick(kit, "medical", "Medical"));
  fillSelect($("lootFocusSelect"), pick(kit, "lootFocus", "LootFocus"));
}

async function refreshConsole() {
  try {
    await loadOptions();
  } catch (error) {
    applyOptions(fallbackOptions);
    setLog(`${error.message || String(error)} Using local dashboard data.`, "warn");
  }

  await refreshAll();
}

async function refreshAll() {
  setPill("connectionPill", "loading", "warn");
  state.profileId = currentProfileId();

  const location = $("mapSelect").value || "tarkovstreets";
  let dashboardError = null;
  let scavRouteError = null;

  try {
    state.dashboard = await request("/api/dashboard/overview");
  } catch (error) {
    dashboardError = error;
  }

  try {
    const [status, dossier, raidPlan] = await Promise.all([
      request("/api/scavlife/status"),
      request("/api/scavlife/dossier"),
      request("/api/scavlife/raid-plan", { location })
    ]);

    state.status = status;
    state.dossier = dossier;
    state.raidPlan = raidPlan;
  } catch (error) {
    scavRouteError = error;
  }

  if (dashboardError && scavRouteError) {
    throw dashboardError;
  }

  render();
  if (scavRouteError) {
    setPill("connectionPill", "local", "warn");
    setLog(`Dashboard refreshed. SPT routes offline: ${scavRouteError.message || String(scavRouteError)}`, "warn");
    return;
  }

  setPill("connectionPill", "online", "ok");
  setLog("Dashboard data refreshed.");
}

function render() {
  const profile = pick(state.status, "profile", "Profile") || {};
  const scav = pick(profile, "activeScav", "ActiveScav") || {};
  const customization = pick(scav, "customization", "Customization") || {};
  const kit = pick(customization, "kitPreferences", "KitPreferences") || {};
  const dossier = pick(state.dossier, "dossier", "Dossier") || pick(profile, "dossier", "Dossier") || {};
  const localScavLife = pick(state.dashboard, "scavLife", "ScavLife") || {};
  const plan = state.raidPlan || {};
  const loadout = pick(plan, "loadoutPlan", "LoadoutPlan") || {};

  setText("scavName", firstDefined(pick(scav, "nickname", "Nickname"), pick(localScavLife, "nickname", "Nickname"), "Unknown Scav"));
  setText("levelValue", firstDefined(pick(scav, "level", "Level"), pick(localScavLife, "level", "Level")));
  setText("xpValue", firstDefined(pick(scav, "experience", "Experience"), pick(localScavLife, "experience", "Experience")));
  setText("conditionValue", firstDefined(pick(state.dossier, "condition", "Condition"), pick(localScavLife, "alive", "Alive") === false ? "missing" : "local"));
  setText("streakValue", firstDefined(pick(dossier, "survivalStreak", "SurvivalStreak"), pick(localScavLife, "survivalStreak", "SurvivalStreak")));
  setText("trustValue", firstDefined(pick(dossier, "trust", "Trust"), pick(localScavLife, "trust", "Trust")));
  setText("stressValue", firstDefined(pick(dossier, "stress", "Stress"), pick(localScavLife, "stress", "Stress")));
  setText("fatigueValue", firstDefined(pick(dossier, "fatigue", "Fatigue"), pick(localScavLife, "fatigue", "Fatigue")));
  setText("lastMapValue", firstDefined(pick(dossier, "lastRaidLocation", "LastRaidLocation"), pick(localScavLife, "lastRaidLocation", "LastRaidLocation")));
  setText("dossierSummary", firstDefined(pick(state.dossier, "summary", "Summary"), buildLocalScavSummary(localScavLife)));
  setText("lastOutcomeValue", firstDefined(pick(dossier, "lastOutcome", "LastOutcome"), pick(localScavLife, "lastOutcome", "LastOutcome")));
  setText("lastCaptureSourceValue", firstDefined(pick(dossier, "lastCaptureSource", "LastCaptureSource"), pick(localScavLife, "lastCaptureSource", "LastCaptureSource")));
  setText("lastLootValue", firstDefined(pick(dossier, "lastRaidLootValue", "LastRaidLootValue"), pick(localScavLife, "totalLootValue", "TotalLootValue")));
  setText("lastItemsValue", firstDefined(pick(dossier, "lastRaidItemsExtracted", "LastRaidItemsExtracted"), pick(localScavLife, "itemsExtracted", "ItemsExtracted")));
  setText("lastKillsValue", firstDefined(pick(dossier, "lastRaidKills", "LastRaidKills"), pick(localScavLife, "kills", "Kills")));
  setText("lastSeenValue", formatUnixTime(pick(dossier, "lastRaidUnixTime", "LastRaidUnixTime")));

  const canDeploy = Boolean(firstDefined(pick(state.status, "canDeploy", "CanDeploy"), pick(localScavLife, "alive", "Alive")));
  setPill("deployPill", canDeploy ? "ready" : "not ready", canDeploy ? "ok" : "warn");

  const risk = pick(plan, "riskLevel", "RiskLevel") || "unknown";
  const riskMode = risk === "low" ? "ok" : risk === "medium" ? "warn" : "bad";
  setPill("riskPill", risk, riskMode);
  setText("planMap", pick(plan, "suggestedMap", "SuggestedMap"));
  setText("planRole", pick(plan, "role", "Role"));
  setText("planExtract", pick(plan, "extractionStyle", "ExtractionStyle"));
  fillLists($("objectivesList"), pick(plan, "objectives", "Objectives"));
  fillLists($("avoidList"), pick(plan, "avoid", "Avoid"));

  setText("budgetTier", pick(loadout, "budgetTier", "BudgetTier"));
  setText("loadoutPrimary", pick(loadout, "primaryWeapon", "PrimaryWeapon"));
  setText("loadoutArmor", pick(loadout, "armor", "Armor"));
  setText("loadoutBackpack", pick(loadout, "backpack", "Backpack"));
  setText("loadoutMedical", pick(loadout, "medical", "Medical"));
  setText("loadoutLoot", pick(loadout, "lootFocus", "LootFocus"));

  renderDashboard();

  $("nicknameInput").value = pick(scav, "nickname", "Nickname") || "";
  $("tagsInput").value = (pick(customization, "tags", "Tags") || []).join(", ");
  setSelectIfPresent("archetypeSelect", pick(customization, "archetype", "Archetype"));
  setSelectIfPresent("homeMapSelect", pick(customization, "homeMap", "HomeMap"));
  setSelectIfPresent("temperamentSelect", pick(customization, "temperament", "Temperament"));
  setSelectIfPresent("voiceSelect", pick(customization, "voice", "Voice"));
  setSelectIfPresent("outfitSelect", pick(customization, "outfitPreset", "OutfitPreset"));
  setSelectIfPresent("primarySelect", pick(kit, "primaryWeapon", "PrimaryWeapon"));
  setSelectIfPresent("armorSelect", pick(kit, "armor", "Armor"));
  setSelectIfPresent("backpackSelect", pick(kit, "backpack", "Backpack"));
  setSelectIfPresent("medicalSelect", pick(kit, "medical", "Medical"));
  setSelectIfPresent("lootFocusSelect", pick(kit, "lootFocus", "LootFocus"));
}

function renderDashboard() {
  const dashboard = state.dashboard || {};
  const processes = pick(dashboard, "processes", "Processes") || {};
  const modStack = pick(dashboard, "modStack", "ModStack") || {};
  const profileHealth = pick(dashboard, "profileHealth", "ProfileHealth") || {};
  const issues = pick(dashboard, "issues", "Issues") || {};
  const trader = pick(dashboard, "traderAvailability", "TraderAvailability") || {};
  const diagnostics = pick(dashboard, "diagnostics", "Diagnostics") || {};
  const quake = pick(dashboard, "quakeBrain", "QuakeBrain") || {};
  const sptLog = pick(dashboard, "sptLog", "SptLog") || {};

  const serverRunning = Boolean(pick(processes, "sptServerRunning", "SptServerRunning"));
  const gameRunning = Boolean(pick(processes, "gameRunning", "GameRunning"));
  const warnings = Number(pick(sptLog, "recentWarningCount", "RecentWarningCount") || 0);
  const errors = Number(pick(sptLog, "recentErrorCount", "RecentErrorCount") || 0);

  setText("sptProcessValue", serverRunning ? "running" : "stopped");
  setText("gameProcessValue", gameRunning ? "running" : "stopped");
  setText("serverModCountValue", pick(modStack, "serverModCount", "ServerModCount"));
  setText("clientPluginCountValue", pick(modStack, "clientPluginCount", "ClientPluginCount"));
  setText("logSignalValue", `${warnings} warn / ${errors} err`);
  const worstIssue = pick(issues, "worstSeverity", "WorstSeverity") || (errors > 0 ? "warn" : "ok");
  setPill("buildHealthPill", worstIssue === "ok" ? "stable" : "review", severityMode(worstIssue));

  const systems = pick(modStack, "systems", "Systems") || [];
  const installedSystems = systems.filter((system) => Boolean(pick(system, "installed", "Installed"))).length;
  setPill("systemsPill", `${installedSystems}/${systems.length}`, installedSystems === systems.length ? "ok" : "warn");
  fillChips($("systemsList"), systems.map((system) => ({
    text: pick(system, "name", "Name"),
    mode: pick(system, "installed", "Installed") ? "ok" : "bad"
  })), "system-chip");

  const traderEnabled = Boolean(pick(trader, "enabled", "Enabled"));
  setPill("traderPill", traderEnabled ? "enabled" : "off", traderEnabled ? "ok" : "warn");
  setText("traderLocationValue", pick(trader, "currentLocation", "CurrentLocation"));
  setText("traderSourceValue", pick(trader, "lastUpdateSource", "LastUpdateSource"));
  setText("traderRaidCounterValue", pick(trader, "raidCounter", "RaidCounter"));
  setText("traderModeValue", pick(trader, "rotationMode", "RotationMode"));
  setText("transitsValue", formatBoolean(Boolean(pick(trader, "transitsEnabled", "TransitsEnabled"))));
  fillChips($("availableTradersList"), (pick(trader, "availableTraders", "AvailableTraders") || []).map((entry) => ({
    text: pick(entry, "name", "Name"),
    mode: "ok"
  })));

  const diagHasData = Boolean(pick(diagnostics, "hasData", "HasData"));
  setPill("diagnosticsPill", diagHasData ? "data" : "no data", diagHasData ? "ok" : "warn");
  setText("diagAvgFps", pick(diagnostics, "avgFps", "AvgFps"));
  setText("diagMinFps", pick(diagnostics, "minFps", "MinFps"));
  setText("diagWorstFrame", formatMs(pick(diagnostics, "worstFrameMs", "WorstFrameMs")));
  setText("diagHitches", pick(diagnostics, "sampleHitches", "SampleHitches"));
  setText("diagMaxBots", pick(diagnostics, "maxAliveBotOwners", "MaxAliveBotOwners"));

  const quakeHasData = Boolean(pick(quake, "hasData", "HasData"));
  setPill("quakePill", quakeHasData ? "data" : "no data", quakeHasData ? "ok" : "warn");
  setText("quakeMap", pick(quake, "map", "Map"));
  setText("quakeEvents", pick(quake, "events", "Events"));
  setText("quakeSnapshots", pick(quake, "snapshots", "Snapshots"));
  setText("quakeMaxBots", pick(quake, "maxBots", "MaxBots"));
  setText("quakeDropped", pick(quake, "droppedLines", "DroppedLines"));

  setPill("sptLogPill", errors > 0 ? `${errors} errors` : `${warnings} warnings`, errors > 0 ? "bad" : warnings > 0 ? "warn" : "ok");
  fillSignals($("serverSignalsList"), pick(sptLog, "recentSignals", "RecentSignals"));

  renderHealthDashboard(profileHealth, issues);
  renderPerformanceDashboard(diagnostics, quake);
  renderModsDashboard(modStack);
  renderLogsDashboard(sptLog);
}

function renderHealthDashboard(profileHealth, issues) {
  const issueItems = pick(issues, "items", "Items") || [];
  const worstSeverity = pick(issues, "worstSeverity", "WorstSeverity") || "ok";
  const issueCount = Number(pick(issues, "count", "Count") || 0);
  setPill("issuePill", issueCount === 0 ? "clear" : `${issueCount} issues`, severityMode(worstSeverity));
  fillIssues($("issueList"), issueItems);

  const profileSeverity = pick(profileHealth, "worstSeverity", "WorstSeverity") || "ok";
  setPill("profileHealthPill", profileSeverity, severityMode(profileSeverity));
  const pmc = pick(profileHealth, "pmc", "Pmc") || {};
  const scav = pick(profileHealth, "scav", "Scav") || {};
  const pmcCounters = pick(pmc, "counters", "Counters") || {};
  const scavCounters = pick(scav, "counters", "Counters") || {};
  const coreFixes = pick(profileHealth, "coreFixes", "CoreFixes") || {};
  const invalidTraders = pick(profileHealth, "invalidTraderIds", "InvalidTraderIds") || [];

  setText("pmcNameValue", pick(pmc, "nickname", "Nickname"));
  setText("pmcLevelValue", pick(pmc, "level", "Level"));
  setText("profileScavNameValue", pick(scav, "nickname", "Nickname"));
  setText("profileScavLevelValue", pick(scav, "level", "Level"));
  setText("knownTraderCountValue", pick(profileHealth, "knownTraderCount", "KnownTraderCount"));
  setText("profileTraderCountValue", pick(profileHealth, "profileTraderCount", "ProfileTraderCount"));
  setText("invalidTraderCountValue", invalidTraders.length);
  setText("fixerFlagsValue", `items ${formatBoolean(Boolean(pick(coreFixes, "removeModItemsFromProfile", "RemoveModItemsFromProfile")))} / traders ${formatBoolean(Boolean(pick(coreFixes, "removeInvalidTradersFromProfile", "RemoveInvalidTradersFromProfile")))}`);

  setText("pmcSessionsValue", pick(pmcCounters, "sessions", "Sessions"));
  setText("pmcKillsValue", pick(pmcCounters, "kills", "Kills"));
  setText("pmcDeathsValue", pick(pmcCounters, "deaths", "Deaths"));
  setText("profileScavSessionsValue", pick(scavCounters, "sessions", "Sessions"));
  setText("profileScavSurvivedValue", pick(scavCounters, "survived", "Survived"));
  setText("profileScavKilledValue", pick(scavCounters, "killed", "Killed"));
  setText("profileScavKillsValue", pick(scavCounters, "kills", "Kills"));
  setText("profileScavDeathsValue", pick(scavCounters, "deaths", "Deaths"));
}

function renderPerformanceDashboard(diagnostics, quake) {
  const hasDiag = Boolean(pick(diagnostics, "hasData", "HasData"));
  const hasQuake = Boolean(pick(quake, "hasData", "HasData"));
  const worstFrame = Number(pick(diagnostics, "worstFrameMs", "WorstFrameMs") || 0);
  const sampleHitches = Number(pick(diagnostics, "sampleHitches", "SampleHitches") || 0);
  setPill("frameHealthPill", hasDiag ? (worstFrame > 250 || sampleHitches > 50 ? "hitchy" : "steady") : "no data", hasDiag ? (worstFrame > 250 || sampleHitches > 50 ? "warn" : "ok") : "warn");
  setPill("telemetryPill", hasQuake ? "full" : hasDiag ? "diagnostics" : "no data", hasDiag || hasQuake ? "ok" : "warn");

  setText("perfAvgFps", pick(diagnostics, "avgFps", "AvgFps"));
  setText("perfMinFps", pick(diagnostics, "minFps", "MinFps"));
  setText("perfWorstFrame", formatMs(pick(diagnostics, "worstFrameMs", "WorstFrameMs")));
  setText("perfWorstP95", formatMs(pick(diagnostics, "worstP95FrameMs", "WorstP95FrameMs")));
  setText("perfHitches", pick(diagnostics, "sampleHitches", "SampleHitches"));
  setText("diagEventCount", formatNumber(pick(diagnostics, "events", "Events")));
  setText("unityWarningCount", pick(diagnostics, "unityWarnings", "UnityWarnings"));
  setText("unityErrorCount", pick(diagnostics, "unityErrors", "UnityErrors"));
  setText("qbEventCount", formatNumber(pick(quake, "events", "Events")));
  setText("qbFileCount", (pick(quake, "recentFiles", "RecentFiles") || []).length);

  fillTable($("hitchTable"), pick(diagnostics, "topHitches", "TopHitches"), [
    { value: (row) => formatMs(pick(row, "frameMs", "FrameMs")) },
    { value: (row) => pick(row, "scene", "Scene") },
    { value: (row) => pick(row, "location", "Location") },
    { value: (row) => pick(row, "aliveBots", "AliveBots") },
    { value: (row) => pick(row, "cpuPercent", "CpuPercent") },
    { value: (row) => `${pick(row, "allocatedMb", "AllocatedMb") || "-"} MB` }
  ]);

  const unityMessages = (pick(diagnostics, "topUnityMessages", "TopUnityMessages") || []).map((entry) => {
    const count = pick(entry, "count", "Count") || 0;
    const level = pick(entry, "level", "Level") || "Log";
    const message = pick(entry, "message", "Message") || "";
    return `${count}x ${level}: ${message}`;
  });
  fillSignals($("unityMessageList"), unityMessages);
}

function renderModsDashboard(modStack) {
  const serverMods = pick(modStack, "serverModDetails", "ServerModDetails") || [];
  const clientPlugins = pick(modStack, "clientPluginDetails", "ClientPluginDetails") || [];
  const customTools = pick(modStack, "customTools", "CustomTools") || [];
  const disabledArchives = pick(modStack, "disabledArchives", "DisabledArchives") || [];

  setPill("serverModsPill", `${serverMods.length}`, "ok");
  setPill("clientPluginsPill", `${clientPlugins.length}`, "ok");
  setPill("disabledArchivePill", `${disabledArchives.length} archived`, disabledArchives.length > 0 ? "warn" : "ok");

  fillTable($("serverModsTable"), serverMods, [
    { value: "name" },
    { value: (row) => formatBoolean(Boolean(pick(row, "hasDll", "HasDll"))) },
    { value: (row) => formatBoolean(Boolean(pick(row, "hasConfig", "HasConfig"))) },
    { value: "lastWriteTime" }
  ]);

  fillTable($("clientPluginsTable"), clientPlugins, [
    { value: "name" },
    { value: "folder" },
    { value: (row) => `${pick(row, "sizeKb", "SizeKb")} KB` }
  ]);

  fillChips($("customToolsList"), customTools.map((tool) => ({
    text: `${pick(tool, "name", "Name")} (${pick(tool, "sourceFiles", "SourceFiles") || 0})`,
    mode: "ok"
  })));
  fillChips($("disabledArchivesList"), disabledArchives.map((archive) => ({
    text: pick(archive, "name", "Name"),
    mode: "warn"
  })));
}

function renderLogsDashboard(sptLog) {
  const routes = pick(sptLog, "topRoutes", "TopRoutes") || [];
  const errors = pick(sptLog, "recentErrors", "RecentErrors") || [];
  setPill("routePill", `${routes.length} routes`, routes.length > 0 ? "ok" : "muted");
  setPill("recentErrorsPill", `${errors.length}`, errors.length > 0 ? "bad" : "ok");

  fillTable($("routeTable"), routes, [
    { value: "route" },
    { value: "count" }
  ]);
  fillSignals($("recentErrorsList"), errors);
}

function setSelectIfPresent(id, value) {
  const select = $(id);
  if (!value) return;
  if ([...select.options].some((option) => option.value === value)) {
    select.value = value;
  }
}

async function applyCustomization() {
  const tags = $("tagsInput").value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);

  await request("/api/scavlife/customization/apply", {
    nickname: $("nicknameInput").value.trim(),
    archetype: $("archetypeSelect").value,
    homeMap: $("homeMapSelect").value,
    temperament: $("temperamentSelect").value,
    voice: $("voiceSelect").value,
    outfitPreset: $("outfitSelect").value,
    tags,
    kitPreferences: {
      primaryWeapon: $("primarySelect").value,
      armor: $("armorSelect").value,
      backpack: $("backpackSelect").value,
      medical: $("medicalSelect").value,
      lootFocus: $("lootFocusSelect").value
    }
  });

  setLog("Customization saved.");
  await refreshAll();
}

async function randomizeCustomization() {
  await request("/api/scavlife/customization/randomize", {
    nickname: $("nicknameInput").value.trim()
  });
  setLog("Customization randomized.");
  await refreshAll();
}

async function resetState() {
  if (!window.confirm("Reset Scav Life state for this profile?")) return;
  await request("/api/scavlife/debug/reset");
  setLog("Profile state reset.");
  await refreshAll();
}

function wireEvents() {
  $("refreshButton").addEventListener("click", () => guard(refreshConsole));
  $("mapSelect").addEventListener("change", () => guard(refreshAll));
  $("profileInput").addEventListener("change", () => guard(refreshAll));
  $("applyButton").addEventListener("click", () => guard(applyCustomization));
  $("randomizeButton").addEventListener("click", () => guard(randomizeCustomization));
  $("resetButton").addEventListener("click", () => guard(resetState));

  for (const tab of document.querySelectorAll(".tab")) {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("is-active"));
      tab.classList.add("is-active");
      $(`${tab.dataset.view}View`).classList.add("is-active");
    });
  }
}

async function guard(action) {
  try {
    await action();
  } catch (error) {
    setPill("connectionPill", "offline", "bad");
    setLog(error.message || String(error), "bad");
  }
}

async function boot() {
  wireEvents();
  await loadConfig();
  applyOptions(fallbackOptions);
  try {
    await refreshConsole();
  } catch (error) {
    setPill("connectionPill", "offline", "bad");
    setLog(`${error.message || String(error)} Start SPT, then press Refresh.`, "bad");
  }
}

guard(boot);
