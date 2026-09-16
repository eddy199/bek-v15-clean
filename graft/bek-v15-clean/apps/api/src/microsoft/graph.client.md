# bek-v15-clean/apps/api/src/microsoft/graph.client.ts

- GraphAddress · type · L27-L29 — type GraphAddress = { emailAddress?: { name?: string; address?: string }; };
- GraphMessage · type · L31-L47 — type GraphMessage = { id?: string; internetMessageId?: string; conversationId?: string; subject?: string | null; from?: GraphAddress; sender?: GraphAddress; toRecipients?: GraphAddress[]; ccRecipients?: GraphAddress[]; receivedDateTime?: string; sentDateTime?: string; body?: { contentType?: string; content?: string }; bodyPreview?: string; internetMessageHeaders?: { name?: string; value?: string }[]; parentFolderId?: string; webLink?: string; };
- MessagePage · type · L49-L52 — type MessagePage = { value?: GraphMessage[]; "@odata.nextLink"?: string; };
- GraphUser · type · L54-L57 — type GraphUser = { mail?: string | null; userPrincipalName?: string | null; };
- GraphFolder · type · L59-L61 — type GraphFolder = { id?: string; };
- GraphClient · class · L64-L102 — class GraphClient
- constructor · method · L65-L65 — constructor(private readonly api: MailboxApiClient)
- me · method · L67-L71 — async me(accessToken: string): Promise<MailboxResult<GraphUser>>
- folder · method · L73-L82 — async folder( accessToken: string, wellKnownName: string, ): Promise<MailboxResult<GraphFolder>>
- listMessages · method · L84-L94 — async listMessages( accessToken: string, options: { after: Date; top: number }, ): Promise<MailboxResult<MessagePage>>
- nextPage · method · L96-L101 — async nextPage( accessToken: string, nextLink: string, ): Promise<MailboxResult<MessagePage>>
