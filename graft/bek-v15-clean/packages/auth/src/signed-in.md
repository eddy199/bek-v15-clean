# bek-v15-clean/packages/auth/src/signed-in.ts

- SignedInHandler · type · L1-L4 — type SignedInHandler = (user: { id: string; email: string; }) => void | Promise<void>;
- onSignedIn · function · L8-L10 — function onSignedIn(handler: SignedInHandler): void
- notifySignedIn · function · L12-L23 — async function notifySignedIn(user: { id: string; email: string; }): Promise<void>
