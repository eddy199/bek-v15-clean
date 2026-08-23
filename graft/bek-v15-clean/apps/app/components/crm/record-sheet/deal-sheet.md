# bek-v15-clean/apps/app/components/crm/record-sheet/deal-sheet.tsx

- Deal · type · L66-L66 — type Deal = RouterOutputs["deals"]["byId"];
- dealCurrency · function · L73-L75 — function dealCurrency(currency: string)
- currencyOptions · function · L77-L86 — function currencyOptions(currency: string)
- ReportedValue · function · L88-L107 — function ReportedValue({ deal }: { deal: Deal })
- DealSheet · function · L123-L246 — function DealSheet({ dealId }: { dealId: string })
- DealOverview · function · L248-L371 — function DealOverview({ deal }: { deal: Deal })
- saveFields · function · L261-L262 — saveFields = (fields: Record<string, FieldValueJson>)
- save · function · L266-L267 — save = (data: Parameters<typeof update.mutate>[0]["data"])
- WhereItStands · function · L373-L430 — function WhereItStands({ deal }: { deal: Deal })
- DealContacts · function · L432-L570 — function DealContacts({ deal, adding, onAdd, onDone, }: { deal: Deal; adding: boolean; onAdd: () => void; onDone: () => void; })
