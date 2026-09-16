# bek-v15-clean/packages/ui/src/components/stat-card.tsx

- TrendDirection · type · L4-L4 — type TrendDirection = "up" | "down" | "neutral";
- StatDelta · type · L6-L10 — type StatDelta = { value: string; direction?: TrendDirection; label?: string; };
- inferDirection · function · L24-L28 — function inferDirection(value: string): TrendDirection
- StatDeltaText · function · L30-L56 — function StatDeltaText({ delta, className, }: { delta: StatDelta; className?: string; })
- StatCard · function · L58-L97 — function StatCard({ label, value, delta, description, className, children, ...props }: Omit<React.ComponentProps<"div">, "title"> & { label?: React.ReactNode; value: React.ReactNode; delta?: StatDelta; description?: React.ReactNode; })
