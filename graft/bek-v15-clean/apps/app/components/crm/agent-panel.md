# bek-v15-clean/apps/app/components/crm/agent-panel.tsx

- AgentPanel · function · L81-L97 — function AgentPanel({ record }: { record: AgentRecord })
- LoadedAgentPanel · function · L99-L135 — function LoadedAgentPanel({ record, history, thread, setThread, }: { record: AgentRecord; history: Conversation[]; thread: string | null; setThread: (thread: string) => void; })
- ThreadWithHistory · function · L140-L184 — function ThreadWithHistory({ record, conversation, onNewThread, }: { record: AgentRecord; conversation: Conversation | null; onNewThread: () => void; })
- Loading · function · L186-L192 — function Loading()
- Thread · function · L194-L322 — function Thread({ record, conversation, thread, onNewThread, }: { record: AgentRecord; conversation: Conversation | null; thread: ThreadState | undefined; onNewThread: () => void; })
- ask · function · L230-L235 — ask = (message: string)
- Idle · function · L324-L359 — function Idle({ kind, onAsk, }: { kind: AgentRecord["kind"]; onAsk: (question: string) => void; })
- Failure · function · L361-L376 — function Failure({ message }: { message: string })
- Item · function · L390-L439 — function Item({ item }: { item: TranscriptItem })
- Sources · function · L441-L462 — function Sources({ sources }: { sources: Source[] })
- AgentAvatar · function · L464-L472 — function AgentAvatar()
- useSavedConversation · function · L474-L534 — function useSavedConversation({ record, conversation, opening, session, messages, }: { record: { contactId?: string; companyId?: string; dealId?: string }; conversation: Conversation | null; opening: React.RefObject<string | null>; session: { sessionId?: string; continuationToken?: string; streamIndex: number; } | null; messages: number; })
