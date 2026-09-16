# bek-v15-clean/apps/api/src/currency/currency.router.ts

- CurrencyRouter · class · L22-L60 — class CurrencyRouter
- constructor · method · L23-L25 — constructor( @Inject(CurrencyService) private readonly currency: CurrencyService, )
- settings · method · L28-L30 — async settings(@Ctx() ctx: AuthedTrpcContext)
- setReportingCurrency · method · L33-L38 — async setReportingCurrency( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof setReportingCurrencyInput>, )
- setManualRate · method · L41-L46 — async setManualRate( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof setManualRateInput>, )
- removeManualRate · method · L49-L54 — async removeManualRate( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof removeManualRateInput>, )
- refreshRates · method · L57-L59 — async refreshRates(@Ctx() ctx: AuthedTrpcContext)
