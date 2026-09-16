# bek-v15-clean/apps/app/app/(app)/[slug]/sales-dashboard.tsx

- Summary · type · L25-L25 — type Summary = RouterOutputs["dashboard"]["summary"];
- changeDelta · function · L32-L44 — function changeDelta( current: number, previous: number, label: string, ): StatDelta | undefined
- SalesDashboard · function · L46-L216 — function SalesDashboard({ summary }: { summary: Summary })
- money · function · L60-L60 — money = (cents: number)
- exact · function · L61-L65 — exact = (value: unknown)
- ChartPanel · function · L218-L236 — function ChartPanel({ title, description, children, }: { title: string; description?: string; children: ReactNode; })
- EmptyChart · function · L238-L244 — function EmptyChart({ label }: { label: string })
