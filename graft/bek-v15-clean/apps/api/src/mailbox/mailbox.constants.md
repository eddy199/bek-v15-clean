# bek-v15-clean/apps/api/src/mailbox/mailbox.constants.ts

- SyncSource · type · L22-L22 — type SyncSource = (typeof SYNC_SOURCES)[number];
- GoogleSyncSource · type · L27-L27 — type GoogleSyncSource = (typeof GOOGLE_SYNC_SOURCES)[number];
- MicrosoftSyncSource · type · L28-L28 — type MicrosoftSyncSource = (typeof MICROSOFT_SYNC_SOURCES)[number];
- isGoogleSyncSource · function · L30-L32 — function isGoogleSyncSource(source: string): source is GoogleSyncSource
- isMicrosoftSyncSource · function · L34-L38 — function isMicrosoftSyncSource( source: string, ): source is MicrosoftSyncSource
