# bek-v15-clean/packages/ui/src/hooks/use-table-selection.ts

- TableSelection · type · L7-L16 — type TableSelection = { ids: string[]; count: number; has: (id: string) => boolean; toggle: (id: string, selected: boolean) => void; toggleAll: (selected: boolean) => void; clear: () => void; allSelected: boolean; someSelected: boolean; };
- useTableSelection · function · L18-L75 — function useTableSelection(rowIds: string[]): TableSelection
