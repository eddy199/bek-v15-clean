# bek-v15-clean/apps/api/src/conversations/conversations.contracts.ts

- hasExactlyOneRecord · function · L9-L14 — hasExactlyOneRecord = (input: { contactId?: string; companyId?: string; dealId?: string; })
- ConversationListInput · type · L22-L22 — type ConversationListInput = z.infer<typeof conversationListInput>;
- ConversationSaveInput · type · L35-L35 — type ConversationSaveInput = z.infer<typeof conversationSaveInput>;
- ConversationEventsInput · type · L44-L44 — type ConversationEventsInput = z.infer<typeof conversationEventsInput>;
- BuilderConversationCreateInput · type · L94-L96 — type BuilderConversationCreateInput = z.infer< typeof builderConversationCreateInput >;
- BuilderConversationSubmitInput · type · L107-L109 — type BuilderConversationSubmitInput = z.infer< typeof builderConversationSubmitInput >;
- BuilderQuestionResponseInput · type · L123-L125 — type BuilderQuestionResponseInput = z.infer< typeof builderQuestionResponseInput >;
- decodedBase64Size · function · L141-L144 — function decodedBase64Size(value: string): number
