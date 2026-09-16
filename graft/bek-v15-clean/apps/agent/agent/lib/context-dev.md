# bek-v15-clean/apps/agent/agent/lib/context-dev.ts

- Brand · type · L5-L35 — type Brand = { domain?: string | null; title?: string | null; description?: string | null; slogan?: string | null; email?: string | null; phone?: string | null; colors?: { hex?: string | null; name?: string | null }[] | null; logos?: | { url?: string | null; mode?: string | null; type?: string | null; colors?: { hex?: string | null; name?: string | null }[] | null; }[] | null; socials?: { type?: string | null; url?: string | null }[] | null; address?: { city?: string | null; state_code?: string | null; country?: string | null; country_code?: string | null; } | null; industries?: { eic?: { industry?: string | null; subindustry?: string | null }[] | null; } | null; links?: { pricing?: string | null; careers?: string | null; } | null; };
- LookupResult · type · L37-L40 — type LookupResult = | { outcome: "found"; brand: Brand; raw: unknown } | { outcome: "skipped"; reason: string } | { outcome: "failed"; reason: string; retryable: boolean };
- SearchResult · type · L42-L47 — type SearchResult = { url: string | null; title: string | null; description: string | null; markdown: string | null; };
- contextDev · function · L53-L66 — async function contextDev(): Promise<ContextDev | null>
- contextDevEnabled · function · L68-L70 — async function contextDevEnabled(): Promise<boolean>
- KeyCheck · type · L72-L75 — type KeyCheck = | { outcome: "valid" } | { outcome: "invalid"; reason: string } | { outcome: "unknown"; reason: string };
- verifyKey · function · L86-L100 — async function verifyKey(key: string): Promise<KeyCheck>
- classifyKey · function · L102-L119 — function classifyKey(error: unknown): KeyCheck
- brandByDomain · function · L121-L131 — async function brandByDomain( domain: string, maxAgeMs?: number, ): Promise<LookupResult>
- brandByEmail · function · L133-L135 — async function brandByEmail(email: string): Promise<LookupResult>
- prefetch · function · L137-L144 — async function prefetch(domain: string): Promise<void>
- extract · function · L146-L170 — async function extract( url: string, schema: Record<string, unknown>, instructions: string, ): Promise< { outcome: "found"; data: unknown } | { outcome: "failed"; reason: string } >
- search · function · L172-L208 — async function search( query: string, options: { limit?: number; excludeDomains?: string[] } = {}, ): Promise< | { outcome: "found"; results: SearchResult[] } | { outcome: "failed"; reason: string } >
- lookup · function · L210-L228 — async function lookup( params: Parameters<ContextDev["brand"]["retrieve"]>[0], ): Promise<LookupResult>
- classify · function · L230-L270 — function classify(error: unknown): LookupResult
- errorCode · function · L272-L275 — function errorCode(error: APIError): string | undefined
- recognisedKeyFailure · function · L277-L288 — function recognisedKeyFailure(error: APIError): boolean
- describe · function · L290-L295 — function describe(error: unknown): string
