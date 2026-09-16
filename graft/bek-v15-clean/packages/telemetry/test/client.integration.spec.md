# bek-v15-clean/packages/telemetry/test/client.integration.spec.ts

- stubFetch · function · L17-L28 — function stubFetch(): void
- decode · function · L30-L41 — async function decode(body: unknown): Promise<unknown>
- restore · function · L63-L70 — function restore(name: string, value: string | undefined): void
- Captured · type · L241-L246 — type Captured = { event: string; distinct_id: string; uuid?: string; properties: Record<string, unknown>; };
- eventOf · function · L248-L258 — function eventOf(body: unknown): Captured
- sentSteps · function · L260-L262 — function sentSteps(): string[]
- installUuid · function · L264-L269 — async function installUuid(): Promise<string>
