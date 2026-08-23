# bek-v15-clean/packages/telemetry/src/client.ts

- Debug · type · L12-L12 — type Debug = (message: string) => void;
- debug · function · L14-L14 — debug: Debug = ()
- onTelemetryProblem · function · L16-L18 — function onTelemetryProblem(sink: Debug | null): void
- posthog · function · L26-L66 — function posthog(): PostHog | null
- resetTelemetryClient · function · L68-L72 — function resetTelemetryClient(): void
- payload · function · L74-L97 — async function payload( properties: Properties, ): Promise<Record<string, unknown> | null>
- capture · function · L99-L101 — function capture(event: string, properties: Properties = {}): void
- captureNow · function · L103-L110 — async function captureNow( event: string, properties: Properties = {}, at?: Date, uuid?: string, ): Promise<boolean>
- send · function · L112-L159 — async function send( event: string, properties: Properties, immediate = false, at?: Date, uuid?: string, ): Promise<boolean>
- flushTelemetry · function · L161-L171 — async function flushTelemetry(): Promise<void>
- shutdownTelemetry · function · L173-L183 — async function shutdownTelemetry(): Promise<void>
