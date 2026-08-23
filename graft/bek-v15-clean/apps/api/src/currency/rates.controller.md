# bek-v15-clean/apps/api/src/currency/rates.controller.ts

- RatesController · class · L17-L61 — class RatesController
- constructor · method · L21-L27 — constructor( private readonly rates: RatesService, private readonly conversion: ConversionService, config: ConfigService<EnvironmentVariables, true>, )
- ratesViaGet · method · L31-L33 — async ratesViaGet(@Headers("authorization") authorization?: string)
- ratesViaPost · method · L37-L39 — async ratesViaPost(@Headers("authorization") authorization?: string)
- run · method · L41-L60 — private async run(authorization?: string)
- timingSafeEquals · function · L63-L72 — function timingSafeEquals(a: string, b: string): boolean
