# bek-v15-clean/packages/ui/src/lib/table-query.ts

- SortDirection · type · L1-L1 — type SortDirection = "asc" | "desc";
- TableQueryState · type · L3-L17 — type TableQueryState = { sort: string; dir: SortDirection; page: number; pageSize: number; tab: string; tabId?: string; filters: Record<string, string>; toggleSort: (id: string) => void; setSort: (id: string) => void; setDir: (dir: SortDirection) => void; setPage: (page: number) => void; setTab: (value: string) => void; setFilter: (id: string, value: string) => void; };
