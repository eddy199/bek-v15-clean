import { ssoClient } from "@better-auth/sso/client";
import { deviceAuthorizationClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient({
	baseURL: typeof window === "undefined" ? undefined : window.location.origin,
	plugins: [ssoClient(), deviceAuthorizationClient()],
});

export const { getSession, signIn, signOut, useSession } = authClient;

export type AuthClient = typeof authClient;
