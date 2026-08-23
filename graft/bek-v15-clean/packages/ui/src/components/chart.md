# bek-v15-clean/packages/ui/src/components/chart.tsx

- TooltipNameType · type · L11-L11 — type TooltipNameType = number | string;
- ChartConfig · type · L13-L22 — type ChartConfig = Record< string, { label?: React.ReactNode; icon?: React.ComponentType; } & ( | { color?: string; theme?: never } | { color?: never; theme: Record<keyof typeof THEMES, string> } ) >;
- ChartContextProps · type · L24-L26 — type ChartContextProps = { config: ChartConfig; };
- useChart · function · L30-L38 — function useChart()
- ChartContainer · function · L40-L81 — function ChartContainer({ id, className, children, config, initialDimension = INITIAL_DIMENSION, ...props }: React.ComponentProps<"div"> & { config: ChartConfig; children: React.ComponentProps< typeof RechartsPrimitive.ResponsiveContainer >["children"]; initialDimension?: { width: number; height: number; }; })
- ChartStyle · function · L83-L114 — ChartStyle = ({ id, config }: { id: string; config: ChartConfig })
- ChartTooltipContent · function · L118-L263 — function ChartTooltipContent({ active, payload, className, indicator = "dot", hideLabel = false, hideIndicator = false, label, labelFormatter, labelClassName, formatter, color, nameKey, labelKey, valueFormatter, }: React.ComponentProps<typeof RechartsPrimitive.Tooltip> & React.ComponentProps<"div"> & { hideLabel?: boolean; hideIndicator?: boolean; indicator?: "line" | "dot" | "dashed"; nameKey?: string; labelKey?: string; valueFormatter?: (value: number | string) => React.ReactNode; } & Omit< RechartsPrimitive.DefaultTooltipContentProps< TooltipValueType, TooltipNameType >, "accessibilityLayer" >)
- ChartLegendContent · function · L267-L320 — function ChartLegendContent({ className, hideIcon = false, payload, verticalAlign = "bottom", nameKey, }: React.ComponentProps<"div"> & { hideIcon?: boolean; nameKey?: string; } & RechartsPrimitive.DefaultLegendContentProps)
- getPayloadConfigFromPayload · function · L322-L356 — function getPayloadConfigFromPayload( config: ChartConfig, payload: unknown, key: string, )
