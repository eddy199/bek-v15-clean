export const API_URL =
	process.env.NEXT_PUBLIC_API_URL ?? "https://bek-v15-clean.vercel.app";

export function isMarketing(): boolean {
	return process.env.IS_MARKETING === "true";
}