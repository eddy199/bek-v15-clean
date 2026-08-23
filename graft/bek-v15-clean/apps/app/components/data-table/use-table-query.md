# bek-v15-clean/apps/app/components/data-table/use-table-query.ts

- TableQuery · type · L11-L14 — type TableQuery<TKey extends string> = { query: TableQueryState; input: ListInput<TKey>; };
- useTableQuery · function · L16-L60 — function useTableQuery<TTab extends string, TFacet extends string>( searchParams: ListSearchParams<TTab, TFacet>, ): TableQuery<TTab | TFacet>
