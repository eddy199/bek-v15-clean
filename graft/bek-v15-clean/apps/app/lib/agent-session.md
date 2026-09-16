# bek-v15-clean/apps/app/lib/agent-session.ts

- Thread · type · L6-L28 — type Thread = | { status: "new"; } | { status: "ready"; session: SessionState; events: readonly MessageStreamEvent[]; } | { status: "working"; session: SessionState; events: readonly MessageStreamEvent[]; } | { status: "ended"; session: SessionState; events: readonly MessageStreamEvent[]; } | { status: "offline"; events: readonly MessageStreamEvent[]; };
- loadThread · function · L30-L50 — async function loadThread( sessionId: string, headers: Record<string, string>, signal?: AbortSignal, ): Promise<Thread>
- offlineThread · function · L52-L54 — function offlineThread(events: readonly MessageStreamEvent[]): Thread
- classify · function · L56-L75 — function classify( session: SessionState, events: readonly MessageStreamEvent[], now: number = Date.now(), ): "ready" | "working" | "ended"
- eventsOf · function · L77-L81 — function eventsOf( thread: Thread | undefined, ): readonly MessageStreamEvent[]
- ComposerState · type · L83-L86 — type ComposerState = { locked: boolean; ended: boolean; };
- composerState · function · L88-L98 — function composerState( thread: Thread | undefined, busy: boolean, ): ComposerState
