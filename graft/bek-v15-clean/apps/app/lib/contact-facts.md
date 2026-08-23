# bek-v15-clean/apps/app/lib/contact-facts.ts

- Contact · type · L3-L3 — type Contact = RouterOutputs["contacts"]["byId"];
- ContactFact · type · L5-L5 — type ContactFact = Contact["facts"][number];
- factsByField · function · L7-L17 — function factsByField(facts: ContactFact[])
