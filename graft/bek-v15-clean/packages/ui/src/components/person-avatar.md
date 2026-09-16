# bek-v15-clean/packages/ui/src/components/person-avatar.tsx

- PersonAvatarSize · type · L7-L7 — type PersonAvatarSize = "sm" | "default" | "lg";
- PersonAvatar · function · L9-L30 — function PersonAvatar({ src, name, email, size = "default", ...props }: Omit<React.ComponentProps<typeof Avatar>, "children" | "size"> & { src?: string | null; name?: string | null; email?: string | null; size?: PersonAvatarSize; })
