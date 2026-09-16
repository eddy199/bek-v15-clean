# bek-v15-clean/apps/app/components/crm/record-sheet/record-stack.ts

- RecordKind · type · L17-L17 — type RecordKind = (typeof RECORD_KINDS)[number];
- RecordRef · type · L19-L19 — type RecordRef = { kind: RecordKind; id: string };
- RecordForm · type · L23-L23 — type RecordForm = (typeof RECORD_FORMS)[number];
- recordKey · function · L40-L42 — function recordKey(ref: RecordRef): string
- parseRef · function · L44-L51 — function parseRef(raw: string): RecordRef | null
- useRecordStack · function · L53-L104 — function useRecordStack()
- useOpenRecord · function · L106-L108 — function useOpenRecord()
- useFieldsSheet · function · L110-L129 — function useFieldsSheet()
- useRecordSheetView · function · L131-L159 — function useRecordSheetView(fallbackTab: string)
