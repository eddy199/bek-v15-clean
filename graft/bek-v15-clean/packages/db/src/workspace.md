# bek-v15-clean/packages/db/src/workspace.ts

- workspaceSlug · function · L26-L38 — function workspaceSlug(name: string): string
- isOnboarded · function · L44-L46 — function isOnboarded(metadata: string | null): boolean
- markOnboarded · function · L48-L56 — function markOnboarded(metadata: string | null, at: Date): string
- readMetadata · function · L58-L72 — function readMetadata(metadata: string | null): Record<string, unknown>
- WorkspaceProfile · type · L74-L80 — type WorkspaceProfile = { website: string; narrative: string; sections: WorkspaceProfileSections; sourceUrl: string | null; refreshedAt: Date; };
- WorkspaceIdentity · type · L82-L86 — type WorkspaceIdentity = { name: string; website: string | null; profile: WorkspaceProfile | null; };
- readWorkspaceProfile · function · L88-L105 — async function readWorkspaceProfile( db: Db, ): Promise<WorkspaceProfile | null>
- websiteUrl · function · L107-L126 — function websiteUrl(website: string | null | undefined): string | null
- profileOf · function · L128-L135 — function profileOf( profile: WorkspaceProfile | null, website: string | null, ): WorkspaceProfile | null
- readWorkspaceIdentity · function · L137-L155 — async function readWorkspaceIdentity( db: Db, ): Promise<WorkspaceIdentity | null>
- writeWorkspaceProfile · function · L157-L190 — async function writeWorkspaceProfile( db: Db, input: { website: string; narrative: string; sections: WorkspaceProfileSections; sourceUrl?: string | null; sessionId?: string | null; }, ): Promise<WorkspaceProfile>
- trimSections · function · L192-L207 — function trimSections( sections: WorkspaceProfileSections, ): WorkspaceProfileSections
- clamp · function · L209-L214 — function clamp(value: string | undefined, max: number): string | undefined
- readSections · function · L216-L230 — function readSections(value: unknown): WorkspaceProfileSections
- text · function · L220-L223 — text = (key: string)
