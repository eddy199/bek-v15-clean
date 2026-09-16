# bek-v15-clean/apps/app/lib/onboarding.ts

- Gate · type · L10-L10 — type Gate = "settled" | "required" | "unknown";
- read · function · L12-L35 — async function read<T>( request: NextRequest, procedure: string, ): Promise<T | null>
- WorkspaceGate · type · L37-L37 — type WorkspaceGate = { gate: Gate; slug: string | null };
- readWorkspaceGate · function · L39-L58 — async function readWorkspaceGate( request: NextRequest, ): Promise<WorkspaceGate>
- readResearchGate · function · L60-L69 — async function readResearchGate(request: NextRequest): Promise<Gate>
