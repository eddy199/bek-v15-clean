# bek-v15-clean/apps/agent/agent/lib/evidence.ts

- EvidenceKind · type · L3-L14 — type EvidenceKind = | "profile.email-match" | "linkedin.employer-and-name" | "crm.thread-reply" | "crm.signature-block" | "github.account-identity" | "crm.meeting-attendance" | "web.cited-claim" | "handle.name-form" | "search.cites-profile" | "employer-only" | "contradiction";
- Weighting · type · L16-L20 — type Weighting = { weight: number; primary: boolean; label: string; };
- Evidence · type · L80-L84 — type Evidence = { kind: EvidenceKind; detail: string; sourceUrl?: string; };
- Scored · type · L86-L91 — type Scored = { score: number; band: FactBand | null; hasPrimary: boolean; rationale: string; };
- scoreEvidence · function · L99-L126 — function scoreEvidence(evidence: Evidence[]): Scored
- bandFor · function · L128-L133 — function bandFor(score: number, hasPrimary: boolean): FactBand | null
- rationaleFor · function · L135-L155 — function rationaleFor( evidence: Evidence[], contradicted: boolean, hasPrimary: boolean, ): string
- joinWords · function · L157-L160 — function joinWords(words: string[]): string
- capitalise · function · L162-L164 — function capitalise(value: string): string
