# bek-v15-clean/apps/app/components/crm/fields/field-editor.tsx

- FieldRecord · type · L76-L76 — type FieldRecord = RouterOutputs["fields"]["list"][number];
- Draft · type · L78-L86 — type Draft = { label: string; type: (typeof FIELD_TYPES)[number]; options: { id?: string; label: string }[]; agentFilled: boolean; agentBrief: string; showOnSheet: boolean; showOnTable: boolean; };
- optionId · function · L101-L103 — function optionId(option: { id?: string }, index: number): string
- draftFrom · function · L107-L121 — function draftFrom(field: FieldRecord | undefined): Draft
- Coverage · function · L123-L170 — function Coverage({ field }: { field: FieldRecord })
- FieldEditor · function · L172-L448 — function FieldEditor({ entity, field, onDone, }: { entity: FieldEntity; field: FieldRecord | undefined; onDone: () => void; })
- patch · function · L192-L193 — patch = (next: Partial<Draft>)
- settle · function · L195-L198 — settle = async ()
- save · function · L224-L241 — save = ()
