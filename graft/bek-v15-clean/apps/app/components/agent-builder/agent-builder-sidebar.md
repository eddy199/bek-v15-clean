# bek-v15-clean/apps/app/components/agent-builder/agent-builder-sidebar.tsx

- Conversation · type · L21-L21 — type Conversation = RouterOutputs["conversations"]["builderList"][number];
- TeamAgent · type · L22-L22 — type TeamAgent = RouterOutputs["agents"]["list"][number];
- SidebarData · type · L23-L27 — type SidebarData = { conversations: Conversation[]; agents: TeamAgent[]; updatedAt: number; };
- AgentBuilderSidebar · function · L29-L156 — function AgentBuilderSidebar({ className, onNavigate, initialData, }: { className?: string; onNavigate?: () => void; initialData?: SidebarData; })
- TeamAgents · function · L158-L203 — function TeamAgents({ agents, pathname, onNavigate, }: { agents: TeamAgent[]; pathname: string; onNavigate?: () => void; })
- ConversationState · function · L205-L231 — function ConversationState({ state }: { state: Conversation["state"] })
- groupConversations · function · L233-L251 — function groupConversations(conversations: Conversation[], now: number)
