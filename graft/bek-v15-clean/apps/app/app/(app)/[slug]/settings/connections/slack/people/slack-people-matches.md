# bek-v15-clean/apps/app/app/(app)/[slug]/settings/connections/slack/people/slack-people-matches.tsx

- SlackSync · type · L12-L12 — type SlackSync = "idle" | "syncing" | "stalled";
- MatchRow · type · L14-L23 — type MatchRow = { crmUserId: string; name: string; email: string; match: { slackUserId: string | null; slackHandle: string | null; slackEmail: string | null; } | null; };
- SlackPeopleMatches · function · L25-L114 — function SlackPeopleMatches({ slug, initialMatches, }: { slug: string; initialMatches: { rows: MatchRow[]; sync: SlackSync }; })
