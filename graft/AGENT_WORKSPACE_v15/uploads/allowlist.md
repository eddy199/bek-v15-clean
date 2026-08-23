# AGENT_WORKSPACE_v15/uploads/allowlist.ts

- AllowedProperty · type · L88-L88 — type AllowedProperty = (typeof ALLOWED_PROPERTIES)[number];
- PropertyValue · type · L92-L97 — type PropertyValue = | string | number | boolean | null | Record<string, number>;
- Properties · type · L99-L99 — type Properties = Partial<Record<AllowedProperty, PropertyValue>>;
- permitted · function · L101-L113 — function permitted( properties: Record<string, unknown>, ): Record<string, PropertyValue>
- permittedTool · function · L163-L165 — function permittedTool(name: string | null | undefined): string
- permittedEvidenceKind · function · L183-L185 — function permittedEvidenceKind(kind: string | null | undefined): string
- permittedMethod · function · L191-L198 — function permittedMethod(method: string | null | undefined): string
- permittedErrorClass · function · L204-L209 — function permittedErrorClass(value: unknown): string
- errorName · function · L211-L222 — function errorName(value: unknown): string
- permittedTaskKind · function · L226-L228 — function permittedTaskKind(kind: string | null | undefined): string
- TelemetrySyncSource · type · L232-L232 — type TelemetrySyncSource = (typeof SYNC_SOURCES)[number];
- permittedSyncSource · function · L236-L238 — function permittedSyncSource(source: string | null | undefined): string
- permittedSyncErrorSource · function · L248-L256 — function permittedSyncErrorSource( source: string | null | undefined, ): string
- permittedRoute · function · L262-L269 — function permittedRoute(route: string | null | undefined): string
- permittedModelId · function · L275-L282 — function permittedModelId(model: string | null | undefined): string
- bucket · function · L294-L300 — function bucket(count: number): string
- dayBucket · function · L310-L316 — function dayBucket(days: number): string
