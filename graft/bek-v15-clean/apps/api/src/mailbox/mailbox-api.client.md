# bek-v15-clean/apps/api/src/mailbox/mailbox-api.client.ts

- MailboxResult · type · L3-L8 — type MailboxResult<T> = | { outcome: "ok"; data: T } | { outcome: "cursor-invalid"; reason: string } | { outcome: "unauthorized"; reason: string } | { outcome: "rate-limited"; reason: string; retryAfterMs: number } | { outcome: "failed"; reason: string; retryable: boolean };
- MailboxApiClient · class · L16-L128 — class MailboxApiClient
- get · method · L19-L53 — async get<T>( url: string, accessToken: string, params: Record<string, string | number | boolean | undefined> = {}, ): Promise<MailboxResult<T>>
- interpret · method · L55-L101 — private async interpret<T>( response: Response, path: string, ): Promise<MailboxResult<T>>
- backoffFrom · method · L103-L111 — private backoffFrom(response: Response): number
- reason · method · L113-L127 — private async reason(response: Response): Promise<string>
