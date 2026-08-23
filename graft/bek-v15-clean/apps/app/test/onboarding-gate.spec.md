# bek-v15-clean/apps/app/test/onboarding-gate.spec.ts

- marketing · function · L20-L23 — function marketing(value: string | undefined)
- stub · function · L25-L28 — function stub(handler: (url: string) => Promise<Response>)
- json · function · L30-L35 — function json(body: unknown, status = 200)
- answerWith · function · L37-L39 — function answerWith(body: unknown, status = 200)
- workspace · function · L41-L45 — workspace = (data: { onboarded: boolean; canRename: boolean; slug?: string; })
- researchKey · function · L47-L49 — researchKey = (configured: boolean)
- setup · function · L52-L76 — function setup({ onboarded = true, canRename = true, configured = true, slug = SLUG, }: { onboarded?: boolean; canRename?: boolean; configured?: boolean; slug?: string; } = {})
- request · function · L78-L82 — function request(pathname: string, cookies: string[] = [])
- redirectedTo · function · L84-L88 — function redirectedTo(response: Response): string | null
- gateOf · function · L90-L92 — async function gateOf(pathname: string)
