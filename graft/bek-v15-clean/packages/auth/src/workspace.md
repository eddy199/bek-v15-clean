# bek-v15-clean/packages/auth/src/workspace.ts

- AllowList · type · L3-L6 — type AllowList = { domains: readonly string[]; addresses: readonly string[]; };
- allowList · function · L13-L29 — function allowList(): AllowList
- workspaceDomains · function · L31-L33 — function workspaceDomains(): readonly string[]
- primaryWorkspaceDomain · function · L35-L37 — function primaryWorkspaceDomain(): string | undefined
- hasSignInAllowList · function · L39-L42 — function hasSignInAllowList(): boolean
- isWorkspaceEmail · function · L44-L61 — function isWorkspaceEmail(email: string | null | undefined): boolean
