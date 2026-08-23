# bek-v15-clean/apps/api/src/slack/slack.router.ts

- SlackRouter · class · L22-L71 — class SlackRouter
- constructor · method · L23-L26 — constructor( @Inject(SlackConnectionService) private readonly connection: SlackConnectionService, )
- status · method · L29-L31 — status(@Ctx() ctx: AuthedTrpcContext)
- matches · method · L34-L36 — matches(@Ctx() ctx: AuthedTrpcContext)
- channels · method · L39-L44 — channels( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof slackChannelsInput>, )
- joinChannel · method · L47-L52 — joinChannel( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof slackJoinChannelInput>, )
- refreshPeople · method · L55-L57 — refreshPeople(@Ctx() ctx: AuthedTrpcContext)
- createChannel · method · L60-L65 — createChannel( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof slackCreateChannelInput>, )
- disconnect · method · L68-L70 — disconnect(@Ctx() ctx: AuthedTrpcContext)
