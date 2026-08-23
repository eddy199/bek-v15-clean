# bek-v15-clean/apps/api/src/google/calendar.client.ts

- GoogleEvent · type · L10-L36 — type GoogleEvent = { id?: string; iCalUID?: string; status?: string; summary?: string; description?: string; location?: string; hangoutLink?: string; htmlLink?: string; recurringEventId?: string; start?: GoogleEventTime; end?: GoogleEventTime; originalStartTime?: GoogleEventTime; organizer?: { email?: string; displayName?: string; self?: boolean }; creator?: { email?: string; displayName?: string; self?: boolean }; attendees?: { email?: string; displayName?: string; responseStatus?: string; organizer?: boolean; self?: boolean; resource?: boolean; }[]; conferenceData?: { entryPoints?: { entryPointType?: string; uri?: string }[]; }; };
- GoogleEventTime · type · L38-L42 — type GoogleEventTime = { dateTime?: string; date?: string; timeZone?: string; };
- EventsPage · type · L44-L48 — type EventsPage = { items?: GoogleEvent[]; nextPageToken?: string; nextSyncToken?: string; };
- EventsQuery · type · L50-L56 — type EventsQuery = { syncToken?: string; timeMin?: string; timeMax?: string; pageToken?: string; maxResults?: number; };
- CalendarClient · class · L59-L79 — class CalendarClient
- constructor · method · L60-L60 — constructor(private readonly api: MailboxApiClient)
- listEvents · method · L62-L78 — async listEvents( accessToken: string, query: EventsQuery, ): Promise<MailboxResult<EventsPage>>
- conferenceUrl · function · L81-L89 — function conferenceUrl(event: GoogleEvent): string | null
- eventTime · function · L91-L105 — function eventTime( time: GoogleEventTime | undefined, ): { at: Date; isAllDay: boolean } | null
