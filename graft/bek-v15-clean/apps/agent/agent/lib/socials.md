# bek-v15-clean/apps/agent/agent/lib/socials.ts

- Network · type · L9-L9 — type Network = "x" | "github";
- SocialProfile · type · L11-L15 — type SocialProfile = { network: Network; handle: string; url: string; };
- Person · type · L17-L24 — type Person = { firstName: string; lastName: string | null; fullName: string; title: string | null; companyName: string | null; companyDomain: string | null; };
- Verdict · type · L26-L28 — type Verdict = | { accepted: true; profile: SocialProfile; evidence: Evidence[] } | { accepted: false; reason: string };
- parseSocialUrl · function · L90-L130 — function parseSocialUrl(raw: string): SocialProfile | null
- extractSocialUrls · function · L132-L147 — function extractSocialUrls(haystack: string[]): SocialProfile[]
- GithubUser · type · L149-L156 — type GithubUser = { login: string; name: string | null; company: string | null; blog: string | null; bio: string | null; type: string; };
- fetchGithubUser · function · L158-L208 — async function fetchGithubUser( handle: string, ): Promise<{ ok: true; user: GithubUser } | { ok: false; reason: string }>
- verifyGithub · function · L210-L293 — async function verifyGithub( profile: SocialProfile, person: Person, ): Promise<Verdict>
- verifyX · function · L295-L372 — async function verifyX( profile: SocialProfile, person: Person, ): Promise<Verdict>
- findSocialCandidates · function · L374-L398 — async function findSocialCandidates( person: Person, network: Network, ): Promise<{ candidates: SocialProfile[]; citations: string[] }>
- str · function · L400-L402 — function str(value: unknown): string | null
