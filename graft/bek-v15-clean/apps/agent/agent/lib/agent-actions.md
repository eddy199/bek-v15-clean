# bek-v15-clean/apps/agent/agent/lib/agent-actions.ts

- AgentActionType · type · L7-L8 — type AgentActionType = (typeof AGENT_ACTION_TYPES)[keyof typeof AGENT_ACTION_TYPES];
- isAgentActionType · function · L16-L18 — function isAgentActionType(value: unknown): value is AgentActionType
- AgentActionDependency · type · L20-L25 — type AgentActionDependency = { readonly id: string; readonly label: string; readonly resourceId: string; readonly fix: string; };
- actionDependency · function · L38-L42 — function actionDependency( type: AgentActionType, ): AgentActionDependency | null
