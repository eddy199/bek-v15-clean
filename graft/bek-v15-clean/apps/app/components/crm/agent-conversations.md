# bek-v15-clean/apps/app/components/crm/agent-conversations.tsx

- Conversation · type · L21-L21 — type Conversation = RouterOutputs["conversations"]["list"][number];
- ConversationPicker · function · L30-L94 — function ConversationPicker({ conversations, current, onSelect, onNew, busy, }: { conversations: Conversation[]; current: Conversation | null; onSelect: (conversation: Conversation) => void; onNew: () => void; busy: boolean; })
- Forget · function · L96-L130 — function Forget({ conversation, onDone, busy, }: { conversation: Conversation; onDone: () => void; busy: boolean; })
- useConversations · function · L132-L138 — function useConversations(recordId: { contactId?: string; companyId?: string; })
- useConversationCache · function · L140-L150 — function useConversationCache()
