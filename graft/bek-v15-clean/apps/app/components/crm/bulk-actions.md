# bek-v15-clean/apps/app/components/crm/bulk-actions.tsx

- BulkResult · type · L30-L35 — type BulkResult = { requested: number; succeeded: number; failed: number; message: string | null; };
- reportBulk · function · L37-L56 — function reportBulk( result: BulkResult, done: (count: number) => string, ): void
- BulkActionsMenu · function · L58-L83 — function BulkActionsMenu({ pending, open, onOpenChange, children, }: { pending?: boolean; open?: boolean; onOpenChange?: (open: boolean) => void; children: ReactNode; })
- BulkOwnerMenu · function · L85-L120 — function BulkOwnerMenu({ users, onSelect, unassignedLabel, }: { users: { id: string; name: string }[]; onSelect: (ownerId: string | null) => void; unassignedLabel?: string; })
- BulkDeleteDialog · function · L122-L152 — function BulkDeleteDialog({ open, onOpenChange, title, description, onConfirm, }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; description: string; onConfirm: () => void; })
