# bek-v15-clean/apps/app/components/crm/record-sheet/record-parts.tsx

- RecordSheetFrame · function · L19-L79 — function RecordSheetFrame({ loading, error, title, description, note, media, actions, stats, tabs, tab, onTabChange, }: { loading: boolean; error: string | null; title: string; description?: ReactNode; note?: ReactNode; media?: ReactNode; actions?: ReactNode; stats?: ReactNode; tabs: DetailSheetTab[]; tab: string; onTabChange: (tab: string) => void; })
- AddRow · function · L81-L105 — function AddRow({ label, columns, onClick, }: { label: string; columns: number; onClick: () => void; })
- DealAmount · function · L107-L118 — function DealAmount({ amountCents, currency, }: { amountCents: number | null; currency: string; })
- MetaLine · function · L120-L152 — function MetaLine({ lead, parts, }: { lead?: ReactNode; parts: (string | null | undefined)[]; })
- DomainLink · function · L154-L176 — function DomainLink({ domain, website, }: { domain: string | null; website: string | null; })
