# bek-v15-clean/apps/app/app/(app)/[slug]/settings/members/members-table.tsx

- Role · type · L34-L34 — type Role = keyof typeof ROLE_LABEL;
- MemberRow · type · L36-L36 — type MemberRow = RouterOutputs["workspace"]["members"]["rows"][number];
- columns · function · L38-L133 — function columns( canChangeRoles: boolean, onChangeRole: (member: MemberRow, role: Role) => void, pending: boolean, ): DataTableColumn<MemberRow>[]
- MembersTable · function · L135-L188 — function MembersTable()
