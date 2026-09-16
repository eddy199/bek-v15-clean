# bek-v15-clean/apps/api/src/companies/companies.router.ts

- CompaniesRouter · class · L27-L93 — class CompaniesRouter
- constructor · method · L28-L30 — constructor( @Inject(CompaniesService) private readonly companies: CompaniesService, )
- list · method · L33-L35 — async list(@Input() input: z.infer<typeof companyListInput>)
- byId · method · L38-L40 — async byId(@Input("id") id: string)
- options · method · L43-L45 — async options(@Input("q") q: string)
- create · method · L48-L50 — async create(@Input() input: z.infer<typeof companyCreateInput>)
- update · method · L53-L55 — async update(@Input() input: z.infer<typeof companyUpdateArgs>)
- delete · method · L58-L60 — async delete(@Input("id") id: string)
- bulkAssignOwner · method · L63-L65 — async bulkAssignOwner(@Input() input: z.infer<typeof companyBulkOwnerInput>)
- bulkEnrich · method · L68-L70 — async bulkEnrich(@Input("ids") ids: string[])
- bulkDelete · method · L73-L75 — async bulkDelete(@Input("ids") ids: string[])
- enrich · method · L78-L80 — async enrich(@Input("id") id: string)
- research · method · L83-L85 — async research(@Ctx() ctx: AuthedTrpcContext, @Input("id") id: string)
- setPrimaryContact · method · L88-L92 — async setPrimaryContact( @Input() input: z.infer<typeof setPrimaryContactInput>, )
