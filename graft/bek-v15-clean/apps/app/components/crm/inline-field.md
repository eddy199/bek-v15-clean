# bek-v15-clean/apps/app/components/crm/inline-field.tsx

- savingField · function · L30-L38 — function savingField(update: { isPending: boolean; variables?: { data?: object } | undefined; }): (field: string) => boolean
- savingValue · function · L40-L46 — function savingValue(update: { isPending: boolean; variables?: { data?: { fields?: Record<string, unknown> } } | undefined; }): (key: string) => boolean
- InlineField · function · L48-L155 — function InlineField({ label, value, onSave, saving = false, placeholder, type = "text", render, provenance, suggestion, }: { label: string; value: string | null; onSave: (next: string) => void; saving?: boolean; placeholder?: string; type?: "text" | "url" | "email" | "tel"; render?: (value: string) => React.ReactNode; provenance?: React.ReactNode; suggestion?: React.ReactNode; })
- commit · function · L73-L76 — commit = ()
- InlineTextCell · function · L157-L227 — function InlineTextCell({ label, value, onSave, saving = false, placeholder, }: { label: string; value: string | null; onSave: (next: string) => void; saving?: boolean; placeholder?: string; })
- commit · function · L173-L176 — commit = ()
- InlineTextArea · function · L229-L297 — function InlineTextArea({ label, value, onSave, saving = false, placeholder, }: { label: string; value: string | null; onSave: (next: string) => void; saving?: boolean; placeholder?: string; })
- commit · function · L245-L248 — commit = ()
- InlineDateField · function · L299-L331 — function InlineDateField({ label, value, onSave, saving = false, placeholder = "—", }: { label: string; value: string | null; onSave: (next: string) => void; saving?: boolean; placeholder?: string; })
- InlineSelectField · function · L333-L372 — function InlineSelectField({ label, value, options, onSave, saving = false, placeholder = "None", }: { label: string; value: string; options: { value: string; label: string }[]; onSave: (next: string) => void; saving?: boolean; placeholder?: string; })
