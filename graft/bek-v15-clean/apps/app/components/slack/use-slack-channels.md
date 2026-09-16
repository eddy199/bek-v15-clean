# bek-v15-clean/apps/app/components/slack/use-slack-channels.ts

- SlackChannelList · type · L12-L22 — type SlackChannelList = { canInviteItself: boolean; channels: PickerChannel[]; fetchingMore: boolean; hasMore: boolean; loadMore: () => void; pending: boolean; reload: () => Promise<unknown>; stalled: boolean; syncing: boolean; };
- useSlackChannels · function · L24-L60 — function useSlackChannels({ enabled = true, query = "", }: { enabled?: boolean; query?: string; } = {}): SlackChannelList
