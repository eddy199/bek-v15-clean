# bek-v15-clean/apps/api/src/trpc/list-input.ts

- ListInput · type · L11-L11 — type ListInput = z.infer<typeof listInput>;
- FacetCounts · type · L13-L13 — type FacetCounts = Record<string, Record<string, number>>;
- ListResult · type · L15-L19 — type ListResult<TRow> = { rows: TRow[]; total: number; facetCounts: FacetCounts; };
- paginate · function · L21-L29 — function paginate(input: Pick<ListInput, "page" | "pageSize">): { skip: number; take: number; }
- resolveOrderBy · function · L31-L38 — function resolveOrderBy<TOrderBy>( input: Pick<ListInput, "sort" | "dir">, columns: Record<string, (dir: "asc" | "desc") => TOrderBy>, fallback: TOrderBy, ): TOrderBy
- countsByKey · function · L40-L55 — function countsByKey< TKey extends string, TGroup extends { _count: { _all: number } } & { [K in TKey]?: string | null; }, >(groups: TGroup[], key: TKey, nullKey?: string): Record<string, number>
- ownerFilter · function · L61-L66 — function ownerFilter( value: string, ): { ownerId: string | null } | undefined
