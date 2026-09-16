# bek-v15-clean/packages/ui/src/components/dashboard-chart.tsx

- Datum · type · L28-L28 — type Datum = Record<string, number | string | null>;
- CartesianProps · type · L30-L41 — type CartesianProps = { data: Datum[]; config: ChartConfig; xKey: string; series?: string[]; className?: string; height?: number; showXAxis?: boolean; showLegend?: boolean; formatX?: (value: string) => string; formatValue?: (value: number | string) => string; };
- seriesKeys · function · L43-L45 — function seriesKeys(config: ChartConfig, series?: string[])
- tooltip · function · L47-L61 — tooltip = ( formatX?: (value: string) => string, formatValue?: (value: number | string) => string, )
- EdgeTick · function · L69-L99 — function EdgeTick({ x, y, payload, index, visibleTicksCount, formatX, }: { x?: number; y?: number; payload?: { value: string | number }; index?: number; visibleTicksCount?: number; formatX?: (value: string) => string; })
- DitherVariant · type · L101-L101 — type DitherVariant = "gradient" | "dotted" | "hatched" | "solid";
- Bloom · type · L102-L102 — type Bloom = "off" | "low" | "high" | "aura";
- bloomFilter · function · L104-L115 — function bloomFilter(bloom: Bloom, color: string)
- ditherPatternId · function · L117-L119 — function ditherPatternId(base: string, key: string)
- ditherFadeId · function · L121-L123 — function ditherFadeId(base: string, key: string)
- DitherDefs · function · L125-L202 — function DitherDefs({ base, keys, variant, }: { base: string; keys: string[]; variant: DitherVariant; })
- AreaTrend · function · L204-L316 — function AreaTrend({ data, config, xKey, series, className, height = 200, showXAxis = true, showLegend = false, formatX, formatValue, stacked = false, variant = "gradient", bloom = "low", }: CartesianProps & { stacked?: boolean; variant?: DitherVariant; bloom?: Bloom; })
- BarTrend · function · L318-L367 — function BarTrend({ data, config, xKey, series, className, height = 180, showXAxis = true, showLegend = false, formatX, formatValue, stacked = false, }: CartesianProps & { stacked?: boolean })
- DonutSlice · type · L369-L369 — type DonutSlice = { key: string; label: string; value: number; color: string };
- BarStat · function · L371-L440 — function BarStat({ data, className, height = 200, onBarClick, formatValue, }: { data: DonutSlice[]; className?: string; height?: number; onBarClick?: (key: string) => void; formatValue?: (value: number | string) => string; })
- DonutStat · function · L442-L549 — function DonutStat({ data, className, height = 200, centerValue, centerLabel, onSliceClick, formatValue, }: { data: DonutSlice[]; className?: string; height?: number; centerValue?: React.ReactNode; centerLabel?: React.ReactNode; onSliceClick?: (key: string) => void; formatValue?: (value: number | string) => string; })
