# bek-v15-clean/apps/agent/agent/lib/agent-manifest.ts

- SlackDestination · type · L90-L90 — type SlackDestination = z.infer<typeof slackDestination>;
- AgentManifestAction · type · L91-L91 — type AgentManifestAction = z.infer<typeof agentManifestAction>;
- AgentManifestTrigger · type · L92-L92 — type AgentManifestTrigger = z.infer<typeof agentManifestTrigger>;
- AgentManifest · type · L93-L93 — type AgentManifest = z.infer<typeof agentManifest>;
- InvalidAgentManifest · class · L95-L100 — class InvalidAgentManifest extends Error
- constructor · method · L96-L99 — constructor(readonly issues: string)
- parseAgentManifest · function · L102-L111 — function parseAgentManifest(value: unknown): AgentManifest
