# bek-v15-clean/packages/auth/src/organization.ts

- WorkspaceRole · type · L10-L10 — type WorkspaceRole = (typeof WORKSPACE_ROLES)[number];
- isWorkspaceRole · function · L12-L14 — function isWorkspaceRole(value: string): value is WorkspaceRole
- isWorkspaceAdmin · function · L16-L18 — function isWorkspaceAdmin(role: WorkspaceRole | null): boolean
- canRenameWorkspace · function · L20-L22 — function canRenameWorkspace(role: WorkspaceRole | null): boolean
- canChangeRole · function · L24-L26 — function canChangeRole(role: WorkspaceRole | null): boolean
- canManageCurrency · function · L28-L30 — function canManageCurrency(role: WorkspaceRole | null): boolean
- canManageConnections · function · L32-L34 — function canManageConnections(role: WorkspaceRole | null): boolean
- canManageTracking · function · L36-L38 — function canManageTracking(role: WorkspaceRole | null): boolean
- ensureWorkspaceMembership · function · L40-L111 — async function ensureWorkspaceMembership( userId: string, ): Promise<string | undefined>
- toWorkspaceRole · function · L113-L115 — function toWorkspaceRole(value: string): WorkspaceRole
- WorkspaceMemberReader · type · L117-L117 — type WorkspaceMemberReader = Pick<Db, "member">;
- workspaceRoleOf · function · L119-L129 — async function workspaceRoleOf( userId: string, client: WorkspaceMemberReader = db, ): Promise<WorkspaceRole | null>
