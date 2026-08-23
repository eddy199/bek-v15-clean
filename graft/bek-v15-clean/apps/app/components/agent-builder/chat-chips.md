# bek-v15-clean/apps/app/components/agent-builder/chat-chips.tsx

- ChatChipVariant · type · L20-L20 — type ChatChipVariant = "default" | "composer";
- ChatChipResource · type · L22-L28 — type ChatChipResource = { kind: "integration" | "company" | "contact" | "deal"; id: string; label: string; detail?: string | null; imageUrl?: string | null; };
- ChatChipAttachment · type · L30-L37 — type ChatChipAttachment = { id?: string; name: string; type: string; size: number; contentBase64?: string; previewUrl?: string | null; };
- ChatReferenceChip · function · L39-L90 — function ChatReferenceChip({ resource, icon, onRemove, variant = "default", }: { resource: ChatChipResource; icon: CarbonIcon; onRemove?: () => void; variant?: ChatChipVariant; })
- ChatReferenceIdentity · function · L92-L125 — function ChatReferenceIdentity({ resource, icon, showDetail = true, compact = false, }: { resource: ChatChipResource; icon: CarbonIcon; showDetail?: boolean; compact?: boolean; })
- ChatAttachmentChip · function · L127-L179 — function ChatAttachmentChip({ attachment, onRemove, variant = "default", }: { attachment: ChatChipAttachment; onRemove?: () => void; variant?: ChatChipVariant; })
- ChatCommandChip · function · L181-L222 — function ChatCommandChip({ label, icon, onRemove, variant = "default", }: { label: string; icon: CarbonIcon; onRemove?: () => void; variant?: ChatChipVariant; })
- formatBytes · function · L224-L228 — function formatBytes(bytes: number): string
- isPreviewableImage · function · L230-L234 — function isPreviewableImage(mediaType: string): boolean
