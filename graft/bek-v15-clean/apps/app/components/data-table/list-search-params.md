# bek-v15-clean/apps/app/components/data-table/list-search-params.ts

- StringParser · type · L13-L13 — type StringParser = ParserBuilder<string> & { defaultValue: string };
- ListParsers · type · L20-L25 — type ListParsers<TKey extends string> = { q: StringParser; sort: StringParser; dir: ParserBuilder<SortDirection> & { defaultValue: SortDirection }; page: ParserBuilder<number> & { defaultValue: number }; } & { [K in TKey]: StringParser };
- ListSearchValues · type · L27-L32 — type ListSearchValues<TKey extends string> = { q: string; sort: string; dir: SortDirection; page: number; } & { [K in TKey]: string };
- ListInput · type · L34-L40 — type ListInput<TKey extends string> = { q: string; sort: string; dir: SortDirection; page: number; pageSize: number; } & { [K in TKey]: string };
- ListTableConfig · type · L42-L49 — type ListTableConfig<TTab extends string, TFacet extends string> = { defaultSort?: string; defaultDir?: SortDirection; pageSize?: number; tabId?: TTab; facetIds?: readonly TFacet[]; facetDefaults?: Partial<Record<TFacet, string>>; };
- ListSearchParams · type · L51-L63 — type ListSearchParams<TTab extends string, TFacet extends string> = { config: ListTableConfig<TTab, TFacet> & { defaultSort: string; defaultDir: SortDirection; pageSize: number; }; parsers: ListParsers<TTab | TFacet>; load: LoaderFunction<ListParsers<TTab | TFacet>>; toInput: ( values: ListSearchValues<TTab | TFacet>, ) => ListInput<TTab | TFacet>; defaultInput: () => ListInput<TTab | TFacet>; };
- createListSearchParams · function · L65-L121 — function createListSearchParams< TTab extends string = never, TFacet extends string = never, >(config: ListTableConfig<TTab, TFacet> = {}): ListSearchParams<TTab, TFacet>
- toInput · function · L98-L112 — toInput = (values: ListSearchValues<TTab | TFacet>)
