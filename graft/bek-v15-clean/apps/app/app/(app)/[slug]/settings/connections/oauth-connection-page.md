# bek-v15-clean/apps/app/app/(app)/[slug]/settings/connections/oauth-connection-page.tsx

- ConnectionQuery · type · L4-L4 — type ConnectionQuery = Record<string, string | string[] | undefined>;
- OAuthConnectionPageProps · type · L6-L11 — type OAuthConnectionPageProps = { connection: React.ComponentType<{ slug: string; connectError?: string }>; params: Promise<{ slug: string }>; provider: string; searchParams: Promise<ConnectionQuery>; };
- OAuthConnectionPage · function · L13-L19 — function OAuthConnectionPage(props: OAuthConnectionPageProps)
- connectErrorOf · function · L21-L23 — function connectErrorOf(query: ConnectionQuery, provider: string)
- OAuthConnectionPageContent · function · L25-L38 — async function OAuthConnectionPageContent({ connection: Connection, params, provider, searchParams, }: OAuthConnectionPageProps)
- first · function · L40-L42 — function first(value: string | string[] | undefined)
