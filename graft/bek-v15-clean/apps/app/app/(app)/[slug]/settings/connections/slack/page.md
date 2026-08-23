# bek-v15-clean/apps/app/app/(app)/[slug]/settings/connections/slack/page.tsx

- SlackConnectionPageProps · type · L53-L56 — type SlackConnectionPageProps = { params: Promise<{ slug: string }>; searchParams: Promise<ConnectionQuery>; };
- SlackConnectionPage · function · L58-L64 — function SlackConnectionPage(props: SlackConnectionPageProps)
- SlackConnectionPageContent · function · L66-L139 — async function SlackConnectionPageContent({ params, searchParams, }: SlackConnectionPageProps)
- toLine · function · L141-L147 — function toLine(entry: SlackScope)
- groupScopes · function · L149-L158 — function groupScopes(scopes: string[])
- ConnectedSlack · function · L160-L278 — function ConnectedSlack({ slug, status, }: { slug: string; status: { workspace: string | null; agents: Array<{ id: string; name: string; description: string | null; status: string; }>; scopes: string[]; canInviteItself: boolean; canManage: boolean; people: { matched: number; reviewed: number }; }; })
- MissingGrant · function · L280-L323 — function MissingGrant({ slug, missing, }: { slug: string; missing: SlackScope[]; })
- PlainList · function · L325-L353 — function PlainList({ title, items, icon, tone, }: { title: string; items: string[]; icon: React.ComponentType; tone: string; })
