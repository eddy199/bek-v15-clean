 
import { Pinecone } from '@pinecone-database/pinecone';

// Initialisation de Pinecone avec la clé de ton .env
const pc = new Pinecone({
  apiKey: process.env.PINECONE_API_KEY || "pcsk_2upiT3_CEeseYqZ2troKPQxXdYU1cis7nk1A5Z8Tsa2DdGzX13NzNusB4K4YYS6rno8aQ9"
});

async function main() {
  const indexName = process.env.PINECONE_INDEX_NAME || "bek-memory";
  
  console.log(`Connexion à l'index Pinecone : ${indexName}...`);
  const index = pc.index(indexName);
  
  // Récupération des stats de l'index pour valider la liaison
  const stats = await index.describeIndexStats();
  console.log("Succès ! Statistiques de l'index Pinecone :", stats);
}

main().catch(console.error);