# bek-v15-clean/apps/api/src/crm/bulk.ts

- BulkResult · type · L14-L19 — type BulkResult = { requested: number; succeeded: number; failed: number; message: string | null; };
- requireOwner · function · L21-L35 — async function requireOwner( db: Db, ownerId: string | null, ): Promise<void>
- runBulk · function · L37-L61 — async function runBulk( ids: string[], act: (id: string) => Promise<unknown>, ): Promise<BulkResult>
