import { fileURLToPath as __eveFileURLToPath } from "node:url";
import { dirname as __eveDirname } from "node:path";
const __filename = __eveFileURLToPath(import.meta.url);
__eveDirname(__filename);
import { L as dispatchScheduleTask } from "../_libs/eve+zod.mjs";
//#region #eve-schedule-task/eve.schedule.c2NoZWR1bGVzL2Rpc3BhdGNoLnRz
const config = { "kind": "production" };
var eve_schedule_default = {
	meta: { description: "Run eve schedule \"dispatch\" from \"schedules/dispatch.ts\"." },
	async run(event) {
		return { result: await dispatchScheduleTask(event.name, config) };
	}
};
//#endregion
export { eve_schedule_default as default };
