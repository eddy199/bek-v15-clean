# bek-v15-clean/packages/auth/src/auth.ts

- Auth · type · L288-L288 — type Auth = typeof auth;
- Session · type · L289-L289 — type Session = typeof auth.$Infer.Session;
- SessionUser · type · L290-L290 — type SessionUser = Session["user"];
- replaceSlackAccount · function · L292-L300 — async function replaceSlackAccount(account: { id: string; accountId: string; providerId: string; }): Promise<void>
- objectValue · function · L302-L304 — function objectValue(value: unknown, key: string): Record<string, unknown>
- recordValue · function · L306-L310 — function recordValue(value: unknown): Record<string, unknown>
- stringValue · function · L312-L318 — function stringValue(value: unknown, key: string): string | undefined
