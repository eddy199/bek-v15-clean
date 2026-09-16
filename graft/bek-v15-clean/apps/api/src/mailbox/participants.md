# bek-v15-clean/apps/api/src/mailbox/participants.ts

- Participant · type · L3-L6 — type Participant = { email: string; name: string | null; };
- parseAddress · function · L42-L55 — function parseAddress(input: string): Participant | null
- parseAddressList · function · L57-L92 — function parseAddressList( header: string | null | undefined, ): Participant[]
- isAutomatedAddress · function · L94-L105 — function isAutomatedAddress(email: string): boolean
- isMachineAddress · function · L112-L120 — function isMachineAddress(email: string): boolean
- isDerivedName · function · L122-L131 — function isDerivedName( email: string, firstName: string, lastName: string | null, ): boolean
- workDomain · function · L133-L135 — function workDomain(email: string): string | null
- ExternalFilterOptions · type · L137-L142 — type ExternalFilterOptions = { ourDomains: ReadonlySet<string>; ourAddresses: ReadonlySet<string>; suppressedDomains: ReadonlySet<string>; suppressedEmails: ReadonlySet<string>; };
- externalParticipants · function · L144-L161 — function externalParticipants( participants: readonly Participant[], options: ExternalFilterOptions, ): Participant[]
- dominantDomain · function · L163-L189 — function dominantDomain( participants: readonly Participant[], preferKnown: ReadonlySet<string> = new Set(), ): string | null
- splitName · function · L191-L224 — function splitName( name: string | null, email: string, ): { firstName: string; lastName: string | null }
- isEmailish · function · L226-L228 — function isEmailish(value: string): boolean
