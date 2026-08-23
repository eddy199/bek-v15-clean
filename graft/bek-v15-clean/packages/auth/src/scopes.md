# bek-v15-clean/packages/auth/src/scopes.ts

- MailboxProviderId · type · L10-L10 — type MailboxProviderId = (typeof MAILBOX_PROVIDER_IDS)[number];
- isMailboxProvider · function · L31-L35 — function isMailboxProvider( providerId: string, ): providerId is MailboxProviderId
- hasSyncScopes · function · L37-L45 — function hasSyncScopes( providerId: string, scope: string | null | undefined, ): boolean
- SignInAccount · type · L47-L50 — type SignInAccount = { providerId: string; scope?: string | null; };
- signsInOnlyWith · function · L52-L60 — function signsInOnlyWith( accounts: readonly SignInAccount[], providerId: string, ): boolean
- signsInWithGoogle · function · L62-L64 — function signsInWithGoogle(accounts: readonly SignInAccount[]): boolean
- signsInWithMicrosoft · function · L66-L70 — function signsInWithMicrosoft( accounts: readonly SignInAccount[], ): boolean
- mailboxGrantsNeeded · function · L72-L91 — function mailboxGrantsNeeded( accounts: readonly SignInAccount[], ): MailboxProviderId[]
- needsMailboxGrant · function · L93-L95 — function needsMailboxGrant(accounts: readonly SignInAccount[]): boolean
- parseScopes · function · L97-L109 — function parseScopes(scope: string | null | undefined): Set<string>
