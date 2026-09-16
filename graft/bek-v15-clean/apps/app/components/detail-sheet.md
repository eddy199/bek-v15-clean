# bek-v15-clean/apps/app/components/detail-sheet.tsx

- DetailSheet · function · L50-L82 — function DetailSheet({ open, onOpenChange, size = "2xl", className, children, }: { open: boolean; onOpenChange: (open: boolean) => void; size?: SheetSize; className?: string; children: ReactNode; })
- DetailSheetHeader · function · L84-L147 — function DetailSheetHeader({ media, title, description, note, actions, onBack, onClose, }: { media?: ReactNode; title: ReactNode; description?: ReactNode; note?: ReactNode; actions?: ReactNode; onBack?: () => void; onClose: () => void; })
- DetailSheetStats · function · L149-L153 — function DetailSheetStats({ children }: { children: ReactNode })
- DetailSheetStat · function · L155-L170 — function DetailSheetStat({ label, children, }: { label: ReactNode; children: ReactNode; })
- DetailSheetTab · type · L172-L178 — type DetailSheetTab = { value: string; label: string; count?: number | null; content: ReactNode; keepMounted?: boolean; };
- DetailSheetTabs · function · L180-L228 — function DetailSheetTabs({ tabs, value, onValueChange, }: { tabs: DetailSheetTab[]; value: string; onValueChange: (value: string) => void; })
- DetailSheetBody · function · L230-L236 — function DetailSheetBody({ children }: { children: ReactNode })
- DetailSheetSection · function · L238-L266 — function DetailSheetSection({ title, action, className, children, }: { title?: ReactNode; action?: ReactNode; className?: string; children: ReactNode; })
- DetailSheetSplit · function · L268-L274 — function DetailSheetSplit({ children }: { children: ReactNode })
- DetailSheetMain · function · L276-L278 — function DetailSheetMain({ children }: { children: ReactNode })
- DetailSheetRail · function · L280-L286 — function DetailSheetRail({ children }: { children: ReactNode })
- DetailSheetProperties · function · L288-L300 — function DetailSheetProperties({ children, columns = 2, }: { children: ReactNode; columns?: 1 | 2; })
- DetailSheetPending · function · L302-L330 — function DetailSheetPending({ fields, running, }: { fields: string[]; running: boolean; })
- DetailSheetProperty · function · L332-L351 — function DetailSheetProperty({ label, wide = false, children, }: { label: ReactNode; wide?: boolean; children: ReactNode; })
- DetailSheetProse · function · L353-L357 — function DetailSheetProse({ children }: { children: ReactNode })
- DetailSheetEmpty · function · L359-L382 — function DetailSheetEmpty({ icon, title, description, action, }: { icon: CarbonIcon; title: string; description: string; action?: ReactNode; })
