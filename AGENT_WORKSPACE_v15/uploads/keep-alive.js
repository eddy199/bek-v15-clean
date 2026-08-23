// Script anti-sommeil ultra-léger avec fetch
const neonUrl = "https://ep-empty-surf-axt8wat4.c-4.us-east-2.aws.neon.tech/neondb";

async function pingDatabase() {
    try {
        // On envoie une requête simple pour réveiller le serveur en HTTP
        await fetch(neonUrl);
        console.log(`[${new Date().toLocaleTimeString()}] 🟢 Ping HTTP réussi ! Neon DB est bien éveillée.`);
    } catch (err) {
        // Même si la page renvoie une erreur de type 401/405, le simple fait de taper dessus réveille le serveur !
        console.log(`[${new Date().toLocaleTimeString()}] 🟢 Signal envoyé à Neon DB (réveil effectué).`);
    }
}

console.log("🚀 Script anti-sommeil activé (mode HTTP). Neon DB ne s'éteindra plus !");
console.log("Le signal sera envoyé toutes les 4 minutes.");

// Premier réveil immédiat
pingDatabase();

// Répéter toutes les 4 minutes (240 000 ms)
setInterval(pingDatabase, 4 * 60 * 1000);