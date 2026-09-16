# bek-v15-clean/apps/app/components/crm/timeline/timeline.tsx

- TimelineAnchor · type · L29-L32 — type TimelineAnchor = | { companyId: string } | { contactId: string } | { dealId: string };
- dayLabel · function · L94-L105 — function dayLabel(day: string, local: boolean): string
- byDay · function · L107-L125 — function byDay(entries: TimelineEntryData[], local: boolean)
- dayKey · function · L127-L135 — function dayKey(value: string, local: boolean): string
- TimelineDay · function · L137-L158 — function TimelineDay({ label, entries, anchor, }: { label: string; entries: TimelineEntryData[]; anchor: TimelineAnchor; })
- Timeline · function · L160-L259 — function Timeline({ anchor }: { anchor: TimelineAnchor })
