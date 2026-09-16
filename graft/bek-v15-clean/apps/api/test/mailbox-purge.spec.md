# bek-v15-clean/apps/api/test/mailbox-purge.spec.ts

- at · function · L42-L44 — function at(hour: number): Date
- Wire · type · L46-L53 — type Wire = { id: string; syncedByUserId: string; provider: "gmail" | "outlook"; sentAt: Date; subject: string; snippet: string; };
- thread · function · L55-L99 — async function thread( rootMessageId: string, companyId: string, messages: Wire[], ): Promise<void>
- seed · function · L101-L167 — async function seed(): Promise<void>
- clean · function · L169-L178 — async function clean(): Promise<void>
- messagesOn · function · L180-L188 — async function messagesOn(rootMessageId: string): Promise<string[]>
- threadState · function · L190-L201 — async function threadState(rootMessageId: string)
- grant · function · L289-L299 — async function grant(scope: string): Promise<void>
- grant · function · L348-L359 — async function grant(scope: string, refreshToken: string | null)
- scopeOf · function · L361-L368 — async function scopeOf(): Promise<string | null | undefined>
