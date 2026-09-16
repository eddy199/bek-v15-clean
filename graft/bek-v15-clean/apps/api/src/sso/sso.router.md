# bek-v15-clean/apps/api/src/sso/sso.router.ts

- headersOf · function · L21-L23 — function headersOf(ctx: BaseTrpcContext): Headers
- SsoRouter · class · L26-L63 — class SsoRouter
- constructor · method · L27-L27 — constructor(@Inject(SsoService) private readonly sso: SsoService)
- signInOptions · method · L30-L32 — async signInOptions()
- settings · method · L36-L38 — async settings(@Ctx() ctx: AuthedTrpcContext)
- list · method · L42-L44 — async list(@Input() input: z.infer<typeof ssoProviderListInput>)
- register · method · L48-L53 — async register( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof registerSsoProviderInput>, )
- remove · method · L57-L62 — async remove( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof deleteSsoProviderInput>, )
