# bek-v15-clean/apps/agent/agent/lib/session-purpose.ts

- SessionPurpose · type · L1-L1 — type SessionPurpose = "builder" | "team-agent" | "research";
- PurposeContext · type · L3-L14 — type PurposeContext = { readonly session: { readonly auth: { readonly current: { readonly attributes: Readonly<Record<string, unknown>>; } | null; readonly initiator: { readonly attributes: Readonly<Record<string, unknown>>; } | null; }; }; };
- purposeOf · function · L16-L20 — function purposeOf(ctx: PurposeContext): SessionPurpose
- attribute · function · L22-L30 — function attribute(ctx: PurposeContext, key: string): string | null
- requireAttribute · function · L32-L36 — function requireAttribute(ctx: PurposeContext, key: string): string
- requireBuilderAttribute · function · L38-L51 — function requireBuilderAttribute( ctx: PurposeContext, key: string, ): string
- requireTeamAgentAttribute · function · L53-L63 — function requireTeamAgentAttribute( ctx: PurposeContext, key: string, ): string
- assertResearchPurpose · function · L65-L69 — function assertResearchPurpose(ctx: PurposeContext): void
