# bek-v15-clean/apps/api/src/agent/agent-runs.service.ts

- AgentRunsService · class · L31-L445 — class AgentRunsService
- constructor · method · L32-L36 — constructor( @InjectDatabase() private readonly db: Db, private readonly access: AgentAccessService, private readonly trigger: AgentTriggerService, )
- list · method · L38-L118 — async list(agentId: string, limit: number, userId: string)
- activity · method · L120-L146 — async activity(agentId: string, limit: number, userId: string)
- runNow · method · L148-L239 — async runNow(input: AgentRunNowInput, userId: string)
- retryRun · method · L241-L331 — async retryRun(input: AgentRetryRunInput, userId: string)
- cancelRun · method · L333-L431 — async cancelRun(input: AgentCancelRunInput, userId: string)
- readableAgent · method · L433-L435 — private async readableAgent(agentId: string, userId: string)
- assertReplayMatches · method · L437-L444 — private assertReplayMatches( existingAgentId: string, requestedAgentId: string, )
