# bek-v15-clean/apps/agent/agent/lib/slack-people.ts

- SlackMember · type · L38-L38 — type SlackMember = z.infer<typeof slackMember>;
- SlackChannel · type · L39-L39 — type SlackChannel = z.infer<typeof slackChannel>;
- SlackPage · type · L40-L44 — type SlackPage = { ok: boolean; error?: string; response_metadata?: { next_cursor?: string | null } | null; };
- requestSlackInventorySync · function · L51-L53 — async function requestSlackInventorySync(): Promise<void>
- requestStaleSlackInventorySync · function · L55-L70 — async function requestStaleSlackInventorySync(): Promise<void>
- runSlackPeopleMatch · function · L72-L128 — async function runSlackPeopleMatch(): Promise<string>
- refreshSlackChannels · function · L130-L139 — async function refreshSlackChannels(): Promise<number>
- visibleChannels · function · L141-L158 — async function visibleChannels( botToken: string, userToken: string | null, ): Promise<SlackChannel[]>
- persistSlackChannels · function · L160-L216 — async function persistSlackChannels( channels: SlackChannel[], canInviteItself: boolean, ): Promise<number>
- listSlackMembers · function · L218-L232 — async function listSlackMembers(accessToken: string): Promise<SlackMember[]>
- listSlackChannels · function · L234-L251 — async function listSlackChannels(accessToken: string): Promise<SlackChannel[]>
- listUrl · function · L253-L265 — function listUrl( method: string, cursor: string, params: Record<string, string> = {}, ): URL
- readSlackPage · function · L267-L282 — async function readSlackPage<Schema extends z.ZodType<SlackPage>>( token: string, url: URL, schema: Schema, operation: string, ): Promise<z.infer<Schema>>
- rejected · function · L284-L296 — function rejected(reason: string, operation: string): Error
