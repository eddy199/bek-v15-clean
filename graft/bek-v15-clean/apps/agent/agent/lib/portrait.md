# bek-v15-clean/apps/agent/agent/lib/portrait.ts

- PortraitResult · type · L5-L10 — type PortraitResult = { stored: boolean; imageUrl: string | null; source?: PortraitSource; reason?: string; };
- storePortrait · function · L12-L87 — async function storePortrait({ contactId, sourceUrl, verified, force = false, }: { contactId: string; sourceUrl: string | null; verified: boolean; force?: boolean; }): Promise<PortraitResult>
- runPortrait · function · L89-L165 — async function runPortrait({ contactId, spend, force = false, }: { contactId: string; spend: (units?: number) => { ok: boolean; reason?: string }; force?: boolean; }): Promise<PortraitResult>
