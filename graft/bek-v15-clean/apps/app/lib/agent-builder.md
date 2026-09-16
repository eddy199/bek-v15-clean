# bek-v15-clean/apps/app/lib/agent-builder.ts

- BuilderCommandType · type · L1-L1 — type BuilderCommandType = "CHAT" | "CREATE_AGENT";
- matchCreateAgentRequest · function · L13-L28 — function matchCreateAgentRequest(message: string): RegExpExecArray | null
- builderCommandType · function · L30-L35 — function builderCommandType(message: string): BuilderCommandType
- consumeBuilderCommand · function · L37-L48 — function consumeBuilderCommand( message: string, ): { commandType: BuilderCommandType; body: string } | null
- consumeBuilderIntent · function · L50-L64 — function consumeBuilderIntent(message: string): { commandType: "CREATE_AGENT"; body: string; invocation: string; } | null
- hasCreateAgentCommand · function · L66-L72 — function hasCreateAgentCommand( submissions: ReadonlyArray<{ commandType: BuilderCommandType }>, ): boolean
