# bek-v15-clean/apps/agent/agent/lib/pool.ts

- collapsing · function · L1-L37 — function collapsing<A extends unknown[]>( run: (...args: A) => Promise<void>, ): (...args: A) => Promise<void>
- invoke · function · L7-L34 — invoke = async (...args: A): Promise<void>
- runLimited · function · L39-L56 — async function runLimited<T>( concurrency: number, items: readonly T[], run: (item: T) => Promise<void>, signal?: AbortSignal, ): Promise<void>
