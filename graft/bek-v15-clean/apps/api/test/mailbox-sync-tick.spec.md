# bek-v15-clean/apps/api/test/mailbox-sync-tick.spec.ts

- Outcome · type · L16-L20 — type Outcome = { source: string; userId: string; status: "synced" | "skipped" | "reconnect" | "rate-limited" | "failed"; };
- FakeState · class · L22-L108 — class FakeState
- add · method · L26-L41 — add(id: string, source: string, overrides: Partial<MailboxSync> = {}): void
- due · method · L43-L45 — async due(now: Date): Promise<MailboxSync[]>
- claim · method · L47-L59 — async claim(row: MailboxSync, now: Date): Promise<boolean>
- release · method · L61-L64 — async release(id: string): Promise<void>
- settle · method · L66-L71 — async settle(id: string): Promise<void>
- markRateLimited · method · L73-L81 — async markRateLimited(id: string, retryAfterMs: number): Promise<void>
- markFailed · method · L83-L92 — async markFailed(id: string, reason: string): Promise<void>
- isDue · method · L94-L98 — private isDue(row: MailboxSync, now: Date): boolean
- write · method · L100-L102 — private write(row: MailboxSync, patch: Partial<MailboxSync>): void
- stamp · method · L104-L107 — private stamp(): Date
- build · function · L114-L127 — function build( state: FakeState, runOne: (userId: string, source: string) => Promise<Outcome | null>, ): MailboxSyncService
