# bek-v15-clean/apps/agent/agent/lib/portrait-sources.ts

- PortraitSource · type · L5-L5 — type PortraitSource = "linkedin" | "github" | "employer-site";
- PortraitCandidate · type · L7-L10 — type PortraitCandidate = { source: PortraitSource; url: string; };
- PortraitSubject · type · L12-L19 — type PortraitSubject = { id: string; name: string | null; linkedinUrl: string | null; githubUrl: string | null; companyName: string | null; companyDomain: string | null; };
- findPortrait · function · L21-L72 — async function findPortrait( subject: PortraitSubject, spend: (units?: number) => { ok: boolean; reason?: string }, ): Promise< | { found: true; candidate: PortraitCandidate } | { found: false; tried: string[]; reason?: string } >
- fromEmployerSite · function · L96-L129 — async function fromEmployerSite( subject: PortraitSubject, ): Promise<PortraitCandidate | null>
- githubLogin · function · L131-L146 — function githubLogin(raw: string | null): string | null
