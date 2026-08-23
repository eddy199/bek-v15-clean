# bek-v15-clean/apps/app/app/(app)/[slug]/settings/agent-model.tsx

- CatalogModel · type · L32-L38 — type CatalogModel = { id: string; name: string; provider: string; contextWindowTokens: number; pricing: { input: number; output: number } | null; };
- perMillion · function · L42-L45 — function perMillion(rate: number): string
- priceHint · function · L47-L50 — function priceHint(model: CatalogModel): string | null
- contextHint · function · L52-L56 — function contextHint(tokens: number): string
- byProvider · function · L58-L68 — function byProvider(models: CatalogModel[]): [string, CatalogModel[]][]
- AgentModel · function · L70-L187 — function AgentModel()
- choose · function · L103-L107 — choose = (id: string)
