# bek-v15-clean/packages/ui/src/components/status-indicator.tsx

- StatusTone · type · L6-L12 — type StatusTone = | "neutral" | "primary" | "info" | "success" | "warning" | "error";
- StatusSize · type · L14-L14 — type StatusSize = "default" | "sm";
- IndicatorDot · function · L30-L66 — function IndicatorDot({ tone = "neutral", color, pulse = false, bloom = "low", className, style, ...props }: React.ComponentProps<"span"> & { tone?: StatusTone; color?: string; pulse?: boolean; bloom?: Bloom; })
- StatusIndicator · function · L68-L112 — function StatusIndicator({ tone = "neutral", color, label, pulse = false, busy = false, bloom = "low", size = "default", className, ...props }: Omit<React.ComponentProps<"span">, "color"> & { tone?: StatusTone; color?: string; label: React.ReactNode; pulse?: boolean; busy?: boolean; bloom?: Bloom; size?: StatusSize; })
