import { join } from "node:path";

const directory = join(import.meta.dir, "..");

// 1. On ignore la vérification locale et les migrations (déjà faites)
// 2. On génère uniquement le client Prisma localement pour que l'app fonctionne.
const generation = await execute([process.execPath, "run", "prisma", "generate"]);

if (generation !== 0) {
	process.exit(generation);
}

console.log("Client Prisma généré avec succès. Migrations ignorées pour Neon DB.");

async function execute(command: string[]): Promise<number> {
	const child = Bun.spawn(command, {
		cwd: directory,
		env: process.env,
		stdin: "inherit",
		stdout: "inherit",
		stderr: "inherit",
	});

	return child.exited;
}