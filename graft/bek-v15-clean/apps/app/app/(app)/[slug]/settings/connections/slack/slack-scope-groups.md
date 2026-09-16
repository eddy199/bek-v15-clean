# bek-v15-clean/apps/app/app/(app)/[slug]/settings/connections/slack/slack-scope-groups.tsx

- ScopeLine · type · L14-L18 — type ScopeLine = { scope: string; grant: string; sensitive: boolean; };
- ScopeGroup · type · L20-L25 — type ScopeGroup = { id: string; label: string; summary: string; scopes: ScopeLine[]; };
- SlackScopeGroups · function · L27-L108 — function SlackScopeGroups({ title, groups, withheld, }: { title: string; groups: ScopeGroup[]; withheld: ScopeLine[]; })
