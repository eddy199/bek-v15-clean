import { db } from "./src/client";

async function pingNeon() {
  try {
    // Utilisation directe du client `db` existant dans le paquet
    await db.$queryRaw`SELECT 1 as alive;`;
    console.log("🟢 [KEEP-ALIVE] Ping réussi :", new Date().toLocaleTimeString());
  } catch (error) {
    console.error("🔴 [KEEP-ALIVE] Erreur :", error);
  }
}

// Premier ping immédiat
pingNeon();

// Répéter toutes les 4 minutes (240000 ms) pour éviter la veille
setInterval(pingNeon, 4 * 60 * 1000);
console.log("🚀 Script Keep-Alive démarré en arrière-plan...");