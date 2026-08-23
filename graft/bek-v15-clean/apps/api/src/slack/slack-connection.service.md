# bek-v15-clean/apps/api/src/slack/slack-connection.service.ts

- SlackConnectionService · class · L29-L278 — class SlackConnectionService
- constructor · method · L30-L35 — constructor( @InjectDatabase() private readonly db: Db, private readonly agent: AgentTriggerService, private readonly slackChannels: SlackChannelsService, private readonly access: AgentAccessService, )
- status · method · L37-L99 — async status(userId: string)
- matches · method · L101-L136 — async matches(userId: string)
- peopleSyncState · method · L138-L155 — private async peopleSyncState(): Promise<SlackSyncState>
- refreshPeople · method · L157-L172 — async refreshPeople(userId: string)
- channels · method · L174-L217 — async channels(input: SlackChannelsInput, userId: string)
- joinChannel · method · L219-L241 — async joinChannel(input: SlackJoinChannelInput, userId: string)
- createChannel · method · L243-L254 — async createChannel(input: SlackCreateChannelInput, userId: string)
- disconnect · method · L256-L277 — async disconnect(userId: string)
