# bek-v15-clean/apps/api/src/google/gmail.client.ts

- GmailMessage · type · L10-L18 — type GmailMessage = { id?: string; threadId?: string; labelIds?: string[]; snippet?: string; internalDate?: string; historyId?: string; payload?: GmailPart; };
- MessageList · type · L20-L24 — type MessageList = { messages?: { id?: string; threadId?: string }[]; nextPageToken?: string; resultSizeEstimate?: number; };
- HistoryList · type · L26-L33 — type HistoryList = { history?: { id?: string; messagesAdded?: { message?: { id?: string; threadId?: string } }[]; }[]; nextPageToken?: string; historyId?: string; };
- Profile · type · L35-L38 — type Profile = { emailAddress?: string; historyId?: string; };
- GmailClient · class · L44-L90 — class GmailClient
- constructor · method · L45-L45 — constructor(private readonly api: MailboxApiClient)
- profile · method · L47-L49 — async profile(accessToken: string): Promise<MailboxResult<Profile>>
- listMessages · method · L51-L68 — async listMessages( accessToken: string, options: { after: Date; before: Date; pageToken?: string; maxResults?: number; }, ): Promise<MailboxResult<MessageList>>
- listHistory · method · L70-L80 — async listHistory( accessToken: string, options: { startHistoryId: string; pageToken?: string }, ): Promise<MailboxResult<HistoryList>>
- getMessage · method · L82-L89 — async getMessage( accessToken: string, id: string, ): Promise<MailboxResult<GmailMessage>>
