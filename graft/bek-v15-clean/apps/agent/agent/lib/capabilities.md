# bek-v15-clean/apps/agent/agent/lib/capabilities.ts

- Capability · type · L8-L14 — type Capability = { readonly id: string; readonly label: string; readonly gives: string; readonly enabled: boolean; readonly from: string; };
- contextDevKey · function · L16-L28 — async function contextDevKey(): Promise<string | null>
- capabilities · function · L30-L32 — async function capabilities(): Promise<readonly Capability[]>
- capabilitiesFrom · function · L34-L70 — function capabilitiesFrom( contextDev: string | null, ): readonly Capability[]
- fromEnv · function · L37-L41 — fromEnv = (id: string)
- enabled · function · L72-L76 — async function enabled(id: string): Promise<boolean>
- unavailable · function · L78-L90 — function unavailable(env: string): { ok: false; configured: false; reason: string; }
- logCapabilities · function · L92-L98 — async function logCapabilities(): Promise<void>
- capabilitiesMarkdown · function · L100-L102 — async function capabilitiesMarkdown(): Promise<string>
- markdownFor · function · L104-L139 — function markdownFor(all: readonly Capability[]): string
