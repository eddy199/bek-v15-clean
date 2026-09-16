# bek-v15-clean/packages/ui/src/components/attendee-list.tsx

- Attendee · type · L14-L21 — type Attendee = { id: string; email: string; name: string | null; responseStatus: string | null; isOrganizer: boolean; imageUrl?: string | null; };
- AttendeeList · function · L37-L93 — function AttendeeList({ attendees, max = 5, className, ...props }: Omit<React.ComponentProps<"div">, "children"> & { attendees: readonly Attendee[]; max?: number; })
