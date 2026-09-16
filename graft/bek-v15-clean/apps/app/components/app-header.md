# bek-v15-clean/apps/app/components/app-header.tsx

- User · type · L31-L31 — type User = { name: string; email: string; image: string | null };
- AppHeader · function · L33-L75 — function AppHeader({ user }: { user: User })
- AppHeaderFallback · function · L77-L101 — function AppHeaderFallback()
- UserMenu · function · L103-L147 — function UserMenu({ user, onSignOut }: { user: User; onSignOut: () => void })
- initials · function · L149-L159 — function initials(name: string): string
