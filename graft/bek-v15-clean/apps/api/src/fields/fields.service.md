# bek-v15-clean/apps/api/src/fields/fields.service.ts

- FieldsService · class · L40-L434 — class FieldsService
- constructor · method · L41-L44 — constructor( @InjectDatabase() private readonly db: Db, private readonly agent: AgentTriggerService, )
- list · method · L46-L57 — async list( entity: FieldEntity, includeArchived: boolean, ): Promise<SerializedField[]>
- byKey · method · L59-L68 — async byKey(entity: FieldEntity, key: string): Promise<SerializedField>
- create · method · L70-L129 — async create(input: FieldCreateInput): Promise<SerializedField>
- update · method · L131-L217 — async update(id: string, data: FieldUpdateData): Promise<SerializedField>
- reorder · method · L219-L241 — async reorder(input: FieldReorderInput): Promise<SerializedField[]>
- archive · method · L243-L255 — async archive(id: string): Promise<SerializedField>
- restore · method · L257-L269 — async restore(id: string): Promise<SerializedField>
- delete · method · L271-L279 — async delete(id: string): Promise<{ id: string }>
- backfill · method · L281-L307 — async backfill(id: string): Promise<{ queued: boolean }>
- coverage · method · L309-L331 — async coverage(id: string): Promise<{ filled: number; total: number }>
- definitionsFor · method · L333-L342 — async definitionsFor( entity: FieldEntity, client: Prisma.TransactionClient = this.db, ): Promise<FieldDefinitionWithOptions[]>
- valuesFor · method · L344-L356 — async valuesFor( entity: FieldEntity, recordId: string, ): Promise<RecordField[]>
- tableValuesFor · method · L358-L401 — async tableValuesFor( entity: FieldEntity, recordIds: string[], ): Promise<Map<string, Record<string, FieldValueJson>>>
- applyValues · method · L403-L422 — async applyValues( tx: Prisma.TransactionClient, entity: FieldEntity, recordId: string, values: Record<string, unknown>, ): Promise<void>
- translate · method · L424-L433 — private translate(error: unknown): unknown
- tableValue · function · L436-L445 — function tableValue( definition: FieldDefinitionWithOptions, value: FieldValueJson, ): FieldValueJson
