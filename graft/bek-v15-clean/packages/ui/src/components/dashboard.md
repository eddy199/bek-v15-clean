# bek-v15-clean/packages/ui/src/components/dashboard.tsx

- StatGroup · function · L4-L26 — function StatGroup({ className, children, ...props }: React.ComponentProps<"div">)
- DashboardGrid · function · L34-L48 — function DashboardGrid({ className, columns = 4, ...props }: React.ComponentProps<"div"> & { columns?: keyof typeof GRID_COLS })
- DashboardRow · function · L50-L70 — function DashboardRow({ className, split = "hero", ...props }: React.ComponentProps<"div"> & { split?: "hero" | "even" })
- ChartCard · function · L72-L117 — function ChartCard({ className, title, description, action, footer, children, ...props }: Omit<React.ComponentProps<"div">, "title"> & { title?: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode; footer?: React.ReactNode; })
- KpiCard · function · L119-L139 — function KpiCard({ className, title, children, ...props }: Omit<React.ComponentProps<"div">, "title"> & { title: React.ReactNode; })
- DashboardSection · function · L141-L176 — function DashboardSection({ className, title, description, action, children, ...props }: Omit<React.ComponentProps<"section">, "title"> & { title?: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode; })
