# bek-v15-clean/apps/api/src/google/gmail-mime.ts

- GmailHeader · type · L7-L7 — type GmailHeader = { name?: string; value?: string };
- GmailPart · type · L9-L15 — type GmailPart = { mimeType?: string; filename?: string; headers?: GmailHeader[]; body?: { data?: string; size?: number; attachmentId?: string }; parts?: GmailPart[]; };
- header · function · L17-L24 — function header( headers: readonly GmailHeader[] | undefined, name: string, ): string | null
- plainTextBody · function · L26-L40 — function plainTextBody(payload: GmailPart | undefined): string
- findPart · function · L42-L55 — function findPart(part: GmailPart, mimeType: string): GmailPart | null
- isAttachment · function · L57-L62 — function isAttachment(part: GmailPart): boolean
- rootMessageId · function · L64-L72 — function rootMessageId( headers: readonly GmailHeader[] | undefined, ): string | null
