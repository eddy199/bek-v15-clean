# bek-v15-clean/apps/app/components/crm/fields/record-fields.tsx

- RecordFieldOption · type · L27-L27 — type RecordFieldOption = { id: string; label: string };
- RecordFieldEntry · type · L29-L37 — type RecordFieldEntry = { id: string; key: string; label: string; type: string; showOnSheet: boolean; options: RecordFieldOption[]; value: FieldValueJson; };
- FieldsCog · function · L45-L59 — function FieldsCog({ kind }: { kind: RecordKind })
- RecordFields · function · L61-L191 — function RecordFields({ fields, saving, onSave, }: { fields: RecordFieldEntry[]; saving: (key: string) => boolean; onSave: (values: Record<string, FieldValueJson>) => void; })
- userOptionsFor · function · L73-L87 — userOptionsFor = (value: string)
- save · function · L94-L95 — save = (value: FieldValueJson)
