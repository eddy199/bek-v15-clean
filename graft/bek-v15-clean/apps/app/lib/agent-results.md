# bek-v15-clean/apps/app/lib/agent-results.ts

- AnchoredResult · type · L3-L3 — type AnchoredResult<T> = { itemId: string; value: T };
- anchorResults · function · L5-L36 — function anchorResults<T>({ items, tool, validate, group, }: { items: readonly TranscriptItem[]; tool: string; validate: (output: unknown) => T | null; group?: ( results: readonly AnchoredResult<T>[], ) => readonly AnchoredResult<T>[]; }): Map<string, T[]>
