# bek-v15-clean/apps/agent/agent/lib/fields.ts

- definitionsFor · function · L20-L28 — async function definitionsFor( entity: FieldEntity, ): Promise<FieldDefinitionWithOptions[]>
- listFields · function · L30-L35 — async function listFields( entity: FieldEntity, ): Promise<SerializedField[]>
- readFields · function · L37-L49 — async function readFields( entity: FieldEntity, recordId: string, ): Promise<RecordField[]>
- WriteResult · type · L51-L53 — type WriteResult = | { written: true; key: string; value: unknown } | { written: false; reason: string };
- writeField · function · L55-L91 — async function writeField(input: { entity: FieldEntity; recordId: string; key: string; value: unknown; }): Promise<WriteResult>
- createField · function · L93-L149 — async function createField(input: { entity: FieldEntity; label: string; type: FieldType; options?: string[]; agentBrief?: string; }): Promise<SerializedField | { created: false; reason: string }>
- updateFieldBrief · function · L151-L176 — async function updateFieldBrief(input: { entity: FieldEntity; key: string; agentBrief: string | null; agentFilled?: boolean; }): Promise<SerializedField | { updated: false; reason: string }>
- archiveField · function · L178-L200 — async function archiveField(input: { entity: FieldEntity; key: string; }): Promise<{ archived: boolean; reason?: string }>
