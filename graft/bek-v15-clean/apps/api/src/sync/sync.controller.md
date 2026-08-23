# bek-v15-clean/apps/api/src/sync/sync.controller.ts

- SyncController · class · L16-L65 — class SyncController
- constructor · method · L20-L25 — constructor( private readonly sync: MailboxSyncService, config: ConfigService<EnvironmentVariables, true>, )
- mailboxesViaGet · method · L29-L31 — async mailboxesViaGet(@Headers("authorization") authorization?: string)
- mailboxesViaPost · method · L35-L37 — async mailboxesViaPost(@Headers("authorization") authorization?: string)
- googleViaGet · method · L41-L43 — async googleViaGet(@Headers("authorization") authorization?: string)
- googleViaPost · method · L47-L49 — async googleViaPost(@Headers("authorization") authorization?: string)
- run · method · L51-L64 — private async run(authorization?: string)
- timingSafeEquals · function · L67-L76 — function timingSafeEquals(a: string, b: string): boolean
