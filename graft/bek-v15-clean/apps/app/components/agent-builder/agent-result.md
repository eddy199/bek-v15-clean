# bek-v15-clean/apps/app/components/agent-builder/agent-result.tsx

- ResultEntry · type · L12-L15 — type ResultEntry = { anchor: (items: readonly TranscriptItem[]) => Map<string, ReactNode[]>; skeleton: ReactNode; };
- defineResult · function · L17-L50 — function defineResult<T>({ tool, validate, group, render, skeleton, }: { tool: string; validate: (output: unknown) => T | null; group?: ( results: readonly { itemId: string; value: T }[], ) => readonly { itemId: string; value: T }[]; render: (result: T, key: string) => ReactNode; skeleton: ReactNode; }): ResultEntry
- hasAgentResult · function · L71-L73 — function hasAgentResult(tool: string): boolean
- agentResultSkeleton · function · L75-L77 — function agentResultSkeleton(tool: string): ReactNode
- agentResultsByItem · function · L79-L93 — function agentResultsByItem( items: readonly TranscriptItem[], ): Map<string, ReactNode[]>
