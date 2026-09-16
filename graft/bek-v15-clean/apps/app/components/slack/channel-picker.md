# bek-v15-clean/apps/app/components/slack/channel-picker.tsx

- PickerChannel · type · L9-L17 — type PickerChannel = { id: string; name: string; memberCount: number | null; isPrivate: boolean; isMember: boolean; classified: boolean; inviteRequestedAt: string | null; };
- ChannelPicker · function · L19-L122 — function ChannelPicker({ canInviteItself, channels, empty, onAdd, onRequest, onSelect, pending = false, value = null, }: { canInviteItself: boolean; channels: PickerChannel[]; empty?: React.ReactNode; onAdd?: (channel: PickerChannel) => void; onRequest?: (channel: PickerChannel) => void; onSelect?: (channel: PickerChannel) => void; pending?: boolean; value?: string | null; })
- describe · function · L124-L135 — function describe(channel: PickerChannel, canInviteItself: boolean): string
