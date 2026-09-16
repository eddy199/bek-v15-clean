# bek-v15-clean/apps/api/src/contacts/contacts.router.ts

- ContactsRouter · class · L27-L91 — class ContactsRouter
- constructor · method · L28-L30 — constructor( @Inject(ContactsService) private readonly contacts: ContactsService, )
- list · method · L33-L35 — async list(@Input() input: z.infer<typeof contactListInput>)
- byId · method · L38-L40 — async byId(@Input("id") id: string)
- create · method · L43-L45 — async create(@Input() input: z.infer<typeof contactCreateInput>)
- update · method · L48-L50 — async update(@Input() input: z.infer<typeof contactUpdateArgs>)
- delete · method · L53-L55 — async delete(@Input("id") id: string)
- enrich · method · L58-L60 — async enrich(@Input("id") id: string)
- bulkAssignOwner · method · L63-L65 — async bulkAssignOwner(@Input() input: z.infer<typeof contactBulkOwnerInput>)
- bulkSetCompany · method · L68-L72 — async bulkSetCompany( @Input() input: z.infer<typeof contactBulkCompanyInput>, )
- bulkEnrich · method · L75-L77 — async bulkEnrich(@Input("ids") ids: string[])
- bulkDelete · method · L80-L82 — async bulkDelete(@Input("ids") ids: string[])
- decideFact · method · L85-L90 — async decideFact( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof factDecisionInput>, )
