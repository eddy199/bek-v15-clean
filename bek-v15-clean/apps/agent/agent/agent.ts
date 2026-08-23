import { DEFAULT_AGENT_MODEL } from "@crm/db/settings";
import { defineAgent, defineDynamic } from "eve";
import { selectedModel } from "./lib/model";

export default defineAgent({
  description: "Comp AI CRM durable agent runtime with BEK-v15 bridge",
  model: defineDynamic({
    fallback: DEFAULT_AGENT_MODEL.id,
    events: {
      "session.started": async () => {
        const configured = await selectedModel();
        return configured
          ? {
              model: configured.model,
              modelContextWindowTokens: configured.modelContextWindowTokens,
            }
          : null;
      },
    },
  }),
});