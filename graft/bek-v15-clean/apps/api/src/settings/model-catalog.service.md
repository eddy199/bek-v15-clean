# bek-v15-clean/apps/api/src/settings/model-catalog.service.ts

- CatalogModel · interface · L13-L19 — interface CatalogModel
- GatewayModel · interface · L21-L29 — interface GatewayModel
- rate · function · L31-L34 — function rate(value: unknown): number | null
- usable · function · L36-L44 — function usable(model: GatewayModel): boolean
- ModelCatalogService · class · L47-L124 — class ModelCatalogService
- constructor · method · L50-L50 — constructor(@Inject(CACHE_MANAGER) private readonly cache: Cache)
- models · method · L52-L61 — async models(): Promise<CatalogModel[] | null>
- find · method · L63-L66 — async find(id: string): Promise<CatalogModel | null>
- fetchCatalog · method · L68-L123 — private async fetchCatalog(): Promise<CatalogModel[] | null>
