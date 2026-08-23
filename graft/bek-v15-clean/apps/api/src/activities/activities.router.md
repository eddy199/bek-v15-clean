# bek-v15-clean/apps/api/src/activities/activities.router.ts

- ActivitiesRouter · class · L24-L59 — class ActivitiesRouter
- constructor · method · L25-L27 — constructor( @Inject(ActivitiesService) private readonly activities: ActivitiesService, )
- timeline · method · L30-L32 — async timeline(@Input() input: z.infer<typeof timelineInput>)
- timelineCounts · method · L35-L37 — async timelineCounts(@Input() input: z.infer<typeof timelineCountsInput>)
- myTasks · method · L40-L45 — async myTasks( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof myTasksInput>, )
- create · method · L48-L53 — async create( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof activityCreateInput>, )
- complete · method · L56-L58 — async complete(@Input() input: z.infer<typeof completeInput>)
