# bek-v15-clean/apps/agent/test/e2e/retry.e2e.ts

- HeldTask · type · L8-L8 — type HeldTask = { id: string; leasedUntil: Date | null };
- record · function · L12-L15 — function record(name: string, ok: boolean, detail: string)
- claimMine · function · L17-L23 — async function claimMine()
- expireLease · function · L25-L30 — async function expireLease(taskId: string)
- holdBackOtherExhausted · function · L32-L53 — async function holdBackOtherExhausted(taskId: string): Promise<HeldTask[]>
- releaseHeldBack · function · L55-L62 — async function releaseHeldBack(held: readonly HeldTask[])
- main · function · L64-L145 — async function main()
