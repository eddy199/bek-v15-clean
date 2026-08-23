# bek-v15-clean/apps/app/components/local-date-time.tsx

- LocalDateTime · function · L19-L34 — function LocalDateTime({ date, options, }: { date: string; options: Intl.DateTimeFormatOptions; })
- LocalDateTimeRange · function · L36-L57 — function LocalDateTimeRange({ start, end, options, }: { start: string; end: string; options: Intl.DateTimeFormatOptions; })
- LocalRelativeDate · function · L59-L67 — function LocalRelativeDate({ date }: { date: string })
- LocalRelativeTime · function · L69-L77 — function LocalRelativeTime({ date }: { date: string })
- LocalDay · function · L79-L89 — function LocalDay({ date }: { date: string })
- LocalDateTimeHydrator · function · L91-L93 — function LocalDateTimeHydrator()
- LocalTime · function · L95-L120 — function LocalTime({ kind, date, end, options, fallback, }: { kind: "date-time" | "date-range" | "day" | "relative-date" | "relative-time"; date: string; end?: string; options?: Intl.DateTimeFormatOptions; fallback: string; })
- formatRelativeDate · function · L122-L127 — function formatRelativeDate(date: string): string
- formatRelativeTime · function · L129-L148 — function formatRelativeTime(date: string): string
- calendarDay · function · L150-L152 — function calendarDay(date: Date): number
- dayDate · function · L154-L156 — function dayDate(day: string): Date
- getDateTimeFormatter · function · L158-L168 — function getDateTimeFormatter( options: Intl.DateTimeFormatOptions, ): Intl.DateTimeFormat
