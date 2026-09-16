# bek-v15-clean/apps/app/proxy.ts

- proxy · function · L23-L55 — async function proxy(request: NextRequest)
- appPath · function · L57-L71 — function appPath(pathname: string, slug: string): string
- isUnder · function · L73-L75 — function isUnder(pathname: string, prefix: string): boolean
- isPublic · function · L77-L79 — function isPublic(pathname: string): boolean
- isUngated · function · L81-L83 — function isUngated(pathname: string): boolean
- isAnonymous · function · L85-L87 — function isAnonymous(pathname: string): boolean
- isSetup · function · L89-L91 — function isSetup(pathname: string): boolean
- sendTo · function · L93-L100 — function sendTo(path: string, request: NextRequest): NextResponse
