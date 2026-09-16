# bek-v15-clean/packages/ui/src/components/simple-table.tsx

- SimpleTableColumn · type · L17-L24 — type SimpleTableColumn = { id: string; header?: ReactNode; srLabel?: string; width?: string; align?: "left" | "right" | "center"; className?: string; };
- SimpleTable · function · L37-L98 — function SimpleTable({ columns, children, variant = "default", surface = "popover", className, containerClassName, headerClassName, headerRowClassName, headerHeight, }: { columns: SimpleTableColumn[]; children: ReactNode; variant?: "default" | "panel"; surface?: keyof typeof PANEL_SURFACE; className?: string; containerClassName?: string; headerClassName?: string; headerRowClassName?: string; headerHeight?: string; })
- SimpleTableRow · function · L100-L119 — function SimpleTableRow({ clickable, expandable, className, ...props }: ComponentProps<typeof TableRow> & { clickable?: boolean; expandable?: boolean; })
