# bek-v15-clean/apps/agent/agent/lib/brand.ts

- BrandResult · type · L6-L12 — type BrandResult = { enriched: boolean; filled?: string[]; mirrored?: string[]; reason?: string; retryable?: boolean; };
- Spend · type · L14-L14 — type Spend = (units?: number) => { ok: boolean; reason?: string };
- FREE · function · L16-L16 — FREE: Spend = ()
- runBrand · function · L44-L139 — async function runBrand({ companyId, fresh = false, spend = FREE, }: { companyId: string; fresh?: boolean; spend?: Spend; }): Promise<BrandResult>
- snapshot · function · L141-L145 — function snapshot<T extends { name: string; domain: string | null }>( company: T, )
- brandOutcome · function · L147-L158 — function brandOutcome(result: BrandResult): string
- settle · function · L160-L169 — async function settle( companyId: string, status: EnrichmentStatus, error: string, ): Promise<void>
