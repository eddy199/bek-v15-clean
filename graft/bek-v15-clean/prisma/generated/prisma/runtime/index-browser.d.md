# bek-v15-clean/prisma/generated/prisma/runtime/index-browser.d.ts

- Args · type · L13-L23 — type Args<T, F extends Operation> = T extends { [K: symbol]: { types: { operations: { [K in F]: { args: any; }; }; }; }; } ? T[symbol]['types']['operations'][F]['args'] : any;
- Exact · type · L29-L31 — type Exact<A, W> = (A extends unknown ? (W extends A ? { [K in keyof A]: Exact<A[K], W[K]>; } : W) : never) | (A extends Narrowable ? A : never);
- GetRuntimeOutput · type · L35-L39 — type GetRuntimeOutput = { id: RuntimeName; prettyName: string; isEdge: boolean; };
- Narrowable · type · L69-L69 — type Narrowable = string | number | bigint | boolean | [];
- Operation · type · L73-L73 — type Operation = 'findFirst' | 'findFirstOrThrow' | 'findUnique' | 'findUniqueOrThrow' | 'findMany' | 'create' | 'createMany' | 'createManyAndReturn' | 'update' | 'updateMany' | 'updateManyAndReturn' | 'upsert' | 'delete' | 'deleteMany' | 'aggregate' | 'count' | 'groupBy' | '$queryRaw' | '$executeRaw' | '$queryRawUnsafe' | '$executeRawUnsafe' | 'findRaw' | 'aggregateRaw' | '$runCommandRaw';
- RuntimeName · type · L82-L82 — type RuntimeName = 'workerd' | 'deno' | 'netlify' | 'node' | 'bun' | 'edge-light' | '';
