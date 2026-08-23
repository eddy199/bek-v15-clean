# bek-v15-clean/packages/ui/src/components/data-table.tsx

- DataTableColumn · type · L60-L73 — type DataTableColumn<TRow> = { id: string; header: ReactNode; cell: (row: TRow) => ReactNode; label?: string; sortable?: boolean; width?: string; align?: "left" | "right" | "center"; headClassName?: string; cellClassName?: string; hideable?: boolean; defaultHidden?: boolean; hideBelow?: "sm" | "md" | "lg"; };
- DataTableFacet · type · L75-L84 — type DataTableFacet = { id: string; label: string; options: { value: string; label: string }[]; searchable?: boolean; search?: string; onSearchChange?: (search: string) => void; stale?: boolean; empty?: ReactNode; };
- DataTableTabs · type · L86-L90 — type DataTableTabs = { id: string; allLabel?: string; options: { value: string; label: string }[]; };
- DataTableExpandable · type · L92-L98 — type DataTableExpandable<TRow, TSub> = { isExpandable: (row: TRow) => boolean; getSubRows: (row: TRow) => TSub[]; getSubRowId: (sub: TSub, row: TRow) => string; renderSubCell: (sub: TSub, columnId: string, row: TRow) => ReactNode; onSubRowClick?: (sub: TSub, row: TRow) => void; };
- DataTableSelection · type · L100-L104 — type DataTableSelection<TRow> = { state: TableSelection; actions: ReactNode; rowLabel?: (row: TRow) => string; };
- DataTableProps · type · L106-L127 — type DataTableProps<TRow, TSub> = { query: TableQueryState; columns: DataTableColumn<TRow>[]; getRowId: (row: TRow) => string; rows: TRow[]; total: number; facetCounts?: Record<string, Record<string, number>>; loading?: boolean; facets?: DataTableFacet[]; tabs?: DataTableTabs; onRowClick?: (row: TRow) => void; onRowHover?: (row: TRow) => void; expandable?: DataTableExpandable<TRow, TSub>; selection?: DataTableSelection<TRow>; actions?: ReactNode; leadingActions?: ReactNode; search?: ReactNode; meta?: ReactNode; empty?: ReactNode; className?: string; tableClassName?: string; };
- columnLabel · function · L141-L144 — function columnLabel<TRow>(column: DataTableColumn<TRow>): string
- SortIndicator · function · L146-L166 — function SortIndicator({ active, dir, }: { active: boolean; dir: "asc" | "desc"; })
- FacetTrigger · function · L168-L178 — function FacetTrigger({ label, ...props }: ComponentProps<typeof Button> & { label: string })
- SearchableFacet · function · L180-L259 — function SearchableFacet({ facet, selected, activeLabel, onSelect, }: { facet: DataTableFacet; selected: string; activeLabel?: string; onSelect: (value: string) => void; })
- choose · function · L205-L209 — choose = (value: string)
- DataTable · function · L261-L798 — function DataTable<TRow, TSub = unknown>({ query, columns, getRowId, rows, total, facetCounts, loading, facets, tabs, onRowClick, onRowHover, expandable, selection, actions, leadingActions, search, meta, empty, className, tableClassName, }: DataTableProps<TRow, TSub>)
- handleClick · function · L659-L671 — handleClick = ()
