# bek-v15-clean/apps/api/src/fields/fields.router.ts

- FieldsRouter · class · L17-L69 — class FieldsRouter
- constructor · method · L18-L18 — constructor(@Inject(FieldsService) private readonly fields: FieldsService)
- list · method · L21-L23 — async list(@Input() input: z.infer<typeof fieldListInput>)
- byKey · method · L26-L28 — async byKey(@Input() input: z.infer<typeof fieldByKeyInput>)
- coverage · method · L31-L33 — async coverage(@Input("id") id: string)
- create · method · L36-L38 — async create(@Input() input: z.infer<typeof fieldCreateInput>)
- update · method · L41-L43 — async update(@Input() input: z.infer<typeof fieldUpdateArgs>)
- reorder · method · L46-L48 — async reorder(@Input() input: z.infer<typeof fieldReorderInput>)
- archive · method · L51-L53 — async archive(@Input("id") id: string)
- restore · method · L56-L58 — async restore(@Input("id") id: string)
- delete · method · L61-L63 — async delete(@Input("id") id: string)
- backfill · method · L66-L68 — async backfill(@Input("id") id: string)
