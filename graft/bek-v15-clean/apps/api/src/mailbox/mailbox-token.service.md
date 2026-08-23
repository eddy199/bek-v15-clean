# bek-v15-clean/apps/api/src/mailbox/mailbox-token.service.ts

- TokenFailure · type · L17-L19 — type TokenFailure = | { outcome: "needs-reconnect"; reason: string } | { outcome: "not-connected"; reason: string };
- TokenResult · type · L21-L21 — type TokenResult = { outcome: "ok"; accessToken: string } | TokenFailure;
- MailboxTokenService · class · L26-L165 — class MailboxTokenService
- constructor · method · L29-L29 — constructor(@InjectDatabase() private readonly db: Db)
- grantedScopes · method · L31-L41 — async grantedScopes( userId: string, providerId: MailboxProviderId, ): Promise<Set<string>>
- isConnected · method · L43-L49 — async isConnected(userId: string, source: SyncSource): Promise<boolean>
- signInAccounts · method · L51-L56 — async signInAccounts(userId: string): Promise<SignInAccount[]>
- hasRefreshToken · method · L58-L68 — async hasRefreshToken( userId: string, providerId: MailboxProviderId, ): Promise<boolean>
- accessTokenFor · method · L70-L110 — async accessTokenFor( userId: string, source: SyncSource, ): Promise<TokenResult>
- revoke · method · L112-L138 — async revoke( userId: string, providerId: MailboxProviderId, ): Promise<boolean>
- revokeWithGoogle · method · L140-L164 — private async revokeWithGoogle(userId: string): Promise<boolean>
- label · function · L167-L169 — function label(providerId: MailboxProviderId): string
