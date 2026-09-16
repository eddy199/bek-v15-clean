# bek-v15-clean/apps/agent/agent/lib/slack-membership.ts

- JoinOutcome · type · L8-L10 — type JoinOutcome = | { joined: true; already: boolean } | { joined: false; reason: string; needsHuman: boolean };
- ChannelState · type · L12-L12 — type ChannelState = { isPrivate: boolean; isMember: boolean };
- call · function · L27-L59 — async function call( token: string, method: string, body: Record<string, string>, attempt = 1, ): Promise<{ ok: boolean; error?: string }>
- botUserId · function · L61-L70 — async function botUserId(token: string): Promise<string | null>
- liveChannelState · function · L72-L100 — async function liveChannelState( token: string, channelId: string, ): Promise<ChannelState | null>
- classifyChannel · function · L102-L125 — async function classifyChannel( channelId: string, cached: ChannelState, token: string, ): Promise<ChannelState>
- joinSlackChannel · function · L127-L178 — async function joinSlackChannel( channelId: string, ): Promise<JoinOutcome>
- inviteWithUserToken · function · L180-L191 — async function inviteWithUserToken( channelId: string, bot: string, ): Promise<{ ok: boolean; error?: string }>
- needsHuman · function · L193-L203 — function needsHuman(error: string): boolean
- explain · function · L205-L223 — function explain(error: string): string
- createSlackChannel · function · L225-L282 — async function createSlackChannel( name: string, isPrivate: boolean, ): Promise<{ id: string; name: string } | { error: string }>
