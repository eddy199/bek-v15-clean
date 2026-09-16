# bek-v15-clean/apps/app/components/agent-clarification-composer.tsx

- ClarificationResponse · type · L22-L24 — type ClarificationResponse = | { requestId: string; optionId: string; text?: never } | { requestId: string; optionId?: never; text: string };
- AgentClarificationComposer · function · L26-L137 — function AgentClarificationComposer({ question, pending, onSubmit, }: { question: EveMessageInputRequest; pending: boolean; onSubmit: (response: ClarificationResponse) => Promise<void>; })
- submit · function · L52-L78 — submit = async (event: FormEvent<HTMLFormElement>)
