# bek-v15-clean/apps/api/src/deals/deals.router.ts

- DealsRouter · class · L31-L104 — class DealsRouter
- constructor · method · L32-L32 — constructor(@Inject(DealsService) private readonly deals: DealsService)
- list · method · L35-L37 — async list(@Input() input: z.infer<typeof dealListInput>)
- byId · method · L40-L42 — async byId(@Input("id") id: string)
- create · method · L45-L47 — async create(@Input() input: z.infer<typeof dealCreateInput>)
- update · method · L50-L52 — async update(@Input() input: z.infer<typeof dealUpdateArgs>)
- delete · method · L55-L57 — async delete(@Input("id") id: string)
- setStage · method · L60-L65 — async setStage( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof setStageInput>, )
- contactOptions · method · L68-L70 — async contactOptions(@Input("dealId") dealId: string)
- attachContact · method · L73-L75 — async attachContact(@Input() input: z.infer<typeof dealAttachContactInput>)
- detachContact · method · L78-L80 — async detachContact(@Input() input: z.infer<typeof dealDetachContactInput>)
- setContactRole · method · L83-L85 — async setContactRole(@Input() input: z.infer<typeof dealContactRoleInput>)
- bulkAssignOwner · method · L88-L90 — async bulkAssignOwner(@Input() input: z.infer<typeof dealBulkOwnerInput>)
- bulkSetStage · method · L93-L98 — async bulkSetStage( @Ctx() ctx: AuthedTrpcContext, @Input() input: z.infer<typeof dealBulkStageInput>, )
- bulkDelete · method · L101-L103 — async bulkDelete(@Input("ids") ids: string[])
