# bek-v15-clean/apps/app/components/crm/fields/field-columns.tsx

- WithFields · type · L12-L12 — type WithFields = { fields: Record<string, string | number | boolean | null> };
- render · function · L14-L32 — function render( type: string, value: string | number | boolean | null, users: Map<string, Owner>, )
- useFieldColumns · function · L34-L68 — function useFieldColumns<Row extends WithFields>( entity: FieldEntity, ): DataTableColumn<Row>[]
