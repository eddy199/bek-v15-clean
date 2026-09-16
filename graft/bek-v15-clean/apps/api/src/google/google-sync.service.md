# bek-v15-clean/apps/api/src/google/google-sync.service.ts

- GoogleSyncService · class · L8-L29 — class GoogleSyncService
- constructor · method · L9-L13 — constructor( private readonly state: SyncStateService, private readonly calendar: CalendarSyncService, private readonly gmail: GmailSyncService, )
- runOne · method · L15-L22 — async runOne(userId: string, source: GoogleSyncSource)
- runForUser · method · L24-L28 — async runForUser(userId: string): Promise<void>
