# bek-v15-clean/apps/api/src/settings/settings.service.ts

- AgentModelSettings · interface · L19-L25 — interface AgentModelSettings
- ModelCatalogResult · interface · L27-L30 — interface ModelCatalogResult
- ResearchKeySettings · interface · L32-L35 — interface ResearchKeySettings
- SettingsService · class · L38-L145 — class SettingsService
- constructor · method · L41-L46 — constructor( @InjectDatabase() private readonly db: Db, private readonly catalog: ModelCatalogService, private readonly researchKeys: ResearchKeyService, private readonly backfill: BackfillService, )
- agentModel · method · L48-L61 — async agentModel(): Promise<AgentModelSettings>
- setAgentModel · method · L63-L94 — async setAgentModel(modelId: string | null): Promise<AgentModelSettings>
- modelCatalog · method · L96-L99 — async modelCatalog(): Promise<ModelCatalogResult>
- researchKey · method · L101-L105 — async researchKey(): Promise<ResearchKeySettings>
- setResearchKey · method · L107-L144 — async setResearchKey(apiKey: string): Promise<ResearchKeySettings>
