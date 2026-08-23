import { createAuthClient } from "better-auth/react";
import { ssoClient } from "@better-auth/sso/client";

export const authClient = createAuthClient({
  baseURL: typeof window !== "undefined" ? window.location.origin : (process.env.NEXT_PUBLIC_APP_URL || "https://bek-v15-clean.vercel.app"),
  plugins: [ssoClient()],
});

export const { signIn, signOut, useSession } = authClient;
