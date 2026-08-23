# bek-v15-clean/apps/agent/test/e2e/slack-delivery.e2e.ts

- Case · type · L5-L9 — type Case = { name: string; destination: { kind: "channel" | "user"; id: string; label: string }; expect: "delivered" | "refused"; };
- main · function · L13-L108 — async function main()
