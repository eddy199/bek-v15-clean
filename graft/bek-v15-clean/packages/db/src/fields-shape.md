# bek-v15-clean/packages/db/src/fields-shape.ts

- FieldEntityName · type · L3-L3 — type FieldEntityName = (typeof FIELD_ENTITIES)[number];
- FieldTypeName · type · L18-L18 — type FieldTypeName = (typeof FIELD_TYPES)[number];
- FieldValueColumn · type · L20-L26 — type FieldValueColumn = | "text" | "number" | "date" | "bool" | "optionId" | "userId";
- columnFor · function · L54-L56 — function columnFor(type: FieldTypeName): FieldValueColumn
- typeLabel · function · L58-L60 — function typeLabel(type: FieldTypeName): string
- usesOptions · function · L62-L64 — function usesOptions(type: FieldTypeName): boolean
- RecordIdColumn · type · L72-L73 — type RecordIdColumn = (typeof RECORD_ID_COLUMNS)[keyof typeof RECORD_ID_COLUMNS];
- recordColumn · function · L75-L77 — function recordColumn(entity: FieldEntityName): RecordIdColumn
- fieldKeyFromLabel · function · L89-L100 — function fieldKeyFromLabel(label: string): string
- FieldValueError · class · L102-L110 — class FieldValueError extends Error
- constructor · method · L105-L109 — constructor(key: string, message: string)
- FieldValueJson · type · L112-L112 — type FieldValueJson = string | number | boolean | null;
