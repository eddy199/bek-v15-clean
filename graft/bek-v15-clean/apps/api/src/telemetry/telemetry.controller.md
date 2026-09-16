# bek-v15-clean/apps/api/src/telemetry/telemetry.controller.ts

- TelemetryController · class · L16-L53 — class TelemetryController
- constructor · method · L20-L25 — constructor( private readonly rollup: RollupService, config: ConfigService<EnvironmentVariables, true>, )
- rollupViaGet · method · L29-L31 — async rollupViaGet(@Headers("authorization") authorization?: string)
- rollupViaPost · method · L35-L37 — async rollupViaPost(@Headers("authorization") authorization?: string)
- run · method · L39-L52 — private async run(authorization?: string)
- timingSafeEquals · function · L55-L64 — function timingSafeEquals(a: string, b: string): boolean
