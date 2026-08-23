# bek-v15-clean/apps/app/lib/trpc/cache.ts

- Settle · type · L6-L6 — type Settle = "all" | "record";
- Options · type · L8-L10 — type Options = { settle?: Settle; };
- RecordKind · type · L12-L12 — type RecordKind = "company" | "contact" | "deal";
- RemovedRecord · type · L14-L14 — type RemovedRecord = { kind: RecordKind; id: string };
- RemovedRecords · type · L16-L16 — type RemovedRecords = { kind: RecordKind; ids: string[] };
- CrmCache · type · L18-L37 — type CrmCache = { company(id?: string, options?: Options): Promise<void>; contact(id?: string, options?: Options): Promise<void>; deal(id?: string, options?: Options): Promise<void>; fields(entity?: RecordKind, options?: Options): Promise<void>; fieldCoverage(id?: string, options?: Options): Promise<void>; removed(record: RemovedRecord): Promise<void>; removedMany(records: RemovedRecords): Promise<void>; conversationRemoved(id: string): Promise<void>; activity(options?: Options): Promise<void>; google(options?: Options): Promise<void>; microsoft(options?: Options): Promise<void>; settings(options?: Options): Promise<void>; currency(options?: Options): Promise<void>; workspace(options?: Options): Promise<void>; slack(options?: Options): Promise<void>; sso(options?: Options): Promise<void>; tracking(options?: Options): Promise<void>; everything(): Promise<void>; };
- useCrmCache · function · L39-L298 — function useCrmCache(): CrmCache
- run · function · L43-L58 — run = ( record: QueryKey[], rest: QueryKey[], { settle = "all" }: Options = {}, ): Promise<void>
- activityKeys · function · L60-L64 — activityKeys = ()
- listKeys · function · L66-L71 — listKeys = ()
- removeRecords · function · L73-L105 — removeRecords = (kind: RecordKind, ids: string[]): Promise<void>
