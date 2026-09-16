# bek-v15-clean/apps/agent/agent/lib/perplexity.ts

- Answer · type · L4-L7 — type Answer = { text: string; citations: string[]; };
- Outcome · type · L9-L9 — type Outcome<T> = { ok: true; data: T } | { ok: false; reason: string };
- perplexityEnabled · function · L11-L13 — function perplexityEnabled(): boolean
- AskOptions · type · L15-L19 — type AskOptions = { model?: "sonar" | "sonar-pro"; domains?: string[]; system?: string; };
- ask · function · L21-L82 — async function ask( question: string, options: AskOptions = {}, ): Promise<Outcome<Answer>>
- findProfileUrls · function · L84-L110 — async function findProfileUrls( terms: string[], companyName: string, ): Promise<string[]>
