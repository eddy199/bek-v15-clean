import { defineTool } from "eve/tools";
import { z } from "zod";

const bekBridgeInputSchema = z.object({
  action: z.enum(["chat", "skill", "fs_read", "fs_write", "fs_list", "memory_search"]),
  query: z.string().min(1),
  skillName: z.string().optional(),
  filePath: z.string().optional(),
  fileContent: z.string().optional(),
  model: z.string().optional(),
  provider: z.enum(["groq", "nvidia", "openrouter", "tokenrouter"]).optional(),
});

export type BekBridgeInput = z.infer<typeof bekBridgeInputSchema>;

export const bekBridgeOutputSchema = z.object({
  ok: z.boolean(),
  result: z.string(),
  error: z.string().optional(),
});

export type BekBridgeOutput = z.infer<typeof bekBridgeOutputSchema>;

const BEK_BASE_URL = process.env.BEK_AGENT_URL || "http://127.0.0.1:8765";

export async function executeBekBridge(input: BekBridgeInput): Promise<BekBridgeOutput> {
  const { action, query, skillName, filePath, fileContent, model, provider } = input;

  try {
    if (action === "chat") {
      const res = await fetch(`${BEK_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [{ role: "user", content: query }],
          provider: provider || "groq",
          model: model,
          use_memory: true,
        }),
      });

      if (!res.ok) {
        return { ok: false, result: "", error: `HTTP ${res.status}: ${await res.text()}` };
      }

      const raw = await res.text();
      const lines = raw.split("\n");
      let fullContent = "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.chunk) {
              fullContent += data.chunk;
            }
          } catch {
            // Ignorer les fragments non-JSON
          }
        }
      }

      return { ok: true, result: fullContent.trim() };
    }

    if (action === "skill") {
      const res = await fetch(`${BEK_BASE_URL}/api/skills/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skill_name: skillName || "codeur",
          input: query,
          provider: provider || "nvidia",
          model: model,
        }),
      });

      if (!res.ok) {
        return { ok: false, result: "", error: `HTTP ${res.status}: ${await res.text()}` };
      }

      const raw = await res.text();
      return { ok: true, result: raw };
    }

    if (action === "fs_read") {
      const res = await fetch(`${BEK_BASE_URL}/api/fs/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: filePath || query }),
      });
      const data = await res.json();
      return { ok: Boolean(data.ok), result: data.content || "", error: data.error };
    }

    if (action === "fs_write") {
      const res = await fetch(`${BEK_BASE_URL}/api/fs/write`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: filePath, content: fileContent || query }),
      });
      const data = await res.json();
      return { ok: Boolean(data.ok), result: data.message || "", error: data.error };
    }

    if (action === "fs_list") {
      const res = await fetch(`${BEK_BASE_URL}/api/fs/list`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: filePath || "" }),
      });
      const data = await res.json();
      return { ok: Boolean(data.ok), result: JSON.stringify(data.items || []), error: data.error };
    }

    if (action === "memory_search") {
      const res = await fetch(`${BEK_BASE_URL}/api/memory/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query, top: 5 }),
      });
      const data = await res.json();
      return { ok: true, result: JSON.stringify(data.results || []) };
    }

    return { ok: false, result: "", error: "Unsupported action" };
  } catch (error) {
    return {
      ok: false,
      result: "",
      error: error instanceof Error ? error.message : "Unknown connection error to BEK agent",
    };
  }
}

export default defineTool({
  description: "Exécute des tâches complexes, recherche en mémoire ou génération de code via le moteur BEK-v15.",
  inputSchema: bekBridgeInputSchema,
  async execute(input) {
    return await executeBekBridge(input);
  },
});