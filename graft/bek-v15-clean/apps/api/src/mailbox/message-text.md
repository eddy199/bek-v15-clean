# bek-v15-clean/apps/api/src/mailbox/message-text.ts

- decodeBase64Url · function · L1-L13 — function decodeBase64Url(data: string): string
- stripHtml · function · L15-L30 — function stripHtml(html: string): string
- stripQuotedHistory · function · L41-L58 — function stripQuotedHistory(body: string): string
- ThreadHeaders · type · L60-L64 — type ThreadHeaders = { references: string | null; inReplyTo: string | null; messageId: string | null; };
- rootMessageIdFrom · function · L66-L78 — function rootMessageIdFrom(headers: ThreadHeaders): string | null
- firstMessageId · function · L80-L83 — function firstMessageId(value: string): string | null
- normaliseMessageId · function · L85-L87 — function normaliseMessageId(value: string): string
- snippetOf · function · L89-L93 — function snippetOf(body: string, limit = 200): string | null
