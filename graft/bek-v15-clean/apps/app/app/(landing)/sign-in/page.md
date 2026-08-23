# bek-v15-clean/apps/app/app/(landing)/sign-in/page.tsx

- SignInOptions · type · L15-L19 — type SignInOptions = { google: boolean; microsoft: boolean; providers: SsoProvider[]; };
- signInOptions · function · L21-L31 — async function signInOptions(): Promise<SignInOptions | null>
- SignInPage · function · L33-L48 — function SignInPage({ searchParams }: PageProps<"/sign-in">)
- SignIn · function · L50-L127 — async function SignIn({ searchParams, }: Pick<PageProps<"/sign-in">, "searchParams">)
