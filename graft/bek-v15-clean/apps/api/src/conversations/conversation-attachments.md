# bek-v15-clean/apps/api/src/conversations/conversation-attachments.ts

- StoredBuilderAttachment · type · L3-L8 — type StoredBuilderAttachment = { id: string; name: string; mediaType: string; size: number; };
- builderMessageWithAttachments · function · L10-L28 — function builderMessageWithAttachments( value: Prisma.JsonValue, attachments: StoredBuilderAttachment[], shareToken?: string, ): Prisma.JsonObject
- isPreviewableImage · function · L30-L34 — function isPreviewableImage(mediaType: string): boolean
- attachmentUrl · function · L36-L39 — function attachmentUrl(id: string, shareToken?: string): string
- recordOf · function · L41-L45 — function recordOf(value: unknown): Record<string, unknown>
