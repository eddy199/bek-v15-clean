# bek-v15-clean/packages/db/src/fields.ts

- FieldDefinitionWithOptions · type · L19-L21 — type FieldDefinitionWithOptions = FieldDefinitionModel & { options: FieldOptionModel[]; };
- SerializedFieldOption · type · L23-L27 — type SerializedFieldOption = { id: string; label: string; position: number; };
- SerializedField · type · L29-L44 — type SerializedField = { id: string; entity: FieldEntity; key: string; label: string; type: FieldType; typeLabel: string; agentFilled: boolean; agentBrief: string | null; required: boolean; showOnSheet: boolean; showOnTable: boolean; position: number; archived: boolean; options: SerializedFieldOption[]; };
- serializeField · function · L46-L72 — function serializeField( definition: FieldDefinitionWithOptions, ): SerializedField
- serializeFieldFor · function · L74-L93 — function serializeFieldFor( definition: FieldDefinitionWithOptions, value: FieldValueJson, ): SerializedField
- coerceValue · function · L99-L192 — function coerceValue( definition: FieldDefinitionWithOptions, input: unknown, ): Partial<Record<FieldValueColumn, unknown>>
- readValue · function · L194-L214 — function readValue( definition: FieldDefinitionWithOptions, row: FieldValueModel | undefined, ): FieldValueJson
- RecordField · type · L216-L216 — type RecordField = SerializedField & { value: FieldValueJson };
- attachValues · function · L218-L232 — function attachValues( definitions: FieldDefinitionWithOptions[], rows: FieldValueModel[], ): RecordField[]
- FieldWriter · type · L234-L249 — type FieldWriter = { fieldValue: { deleteMany(args: { where: Record<string, unknown> }): Promise<unknown>; upsert(args: { where: Record<string, unknown>; create: Record<string, unknown>; update: Record<string, unknown>; }): Promise<unknown>; }; user: { findMany(args: { where: { id: { in: string[] } }; select: { id: true }; }): Promise<{ id: string }[]>; }; };
- writeValues · function · L251-L295 — async function writeValues( tx: FieldWriter, entity: FieldEntity, recordId: string, definitions: FieldDefinitionWithOptions[], values: Record<string, unknown>, ): Promise<void>
- PendingWrite · type · L297-L300 — type PendingWrite = { definition: FieldDefinitionWithOptions; stored: unknown; };
- assertUsersExist · function · L302-L328 — async function assertUsersExist( tx: FieldWriter, writes: PendingWrite[], ): Promise<void>
