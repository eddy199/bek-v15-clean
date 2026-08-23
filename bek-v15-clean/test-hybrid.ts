import { PrismaClient } from './prisma/generated/prisma';
import { PrismaPg } from '@prisma/adapter-pg';
import pkg from 'pg';
const { Pool } = pkg;
import { Pinecone } from '@pinecone-database/pinecone';

const connectionString = process.env.DATABASE_URL || "postgresql://neondb_owner:npg_FqRIu3UOyPJ8@ep-misty-dream-ay7lX9lc.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require";
const pool = new Pool({ connectionString });
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter });

const pc = new Pinecone({
  apiKey: process.env.PINECONE_API_KEY || "pcsk_2upiT3_CEeseYqZ2troKPQxXdYU1cis7nk1A5Z8Tsa2DdGzX13NzNusB4K4YYS6rno8aQ9"
});

async function main() {
  console.log("1. Test d'écriture d'un log dans Neon via l'adaptateur Prisma 7...");
  const newLog = await prisma.log.create({
    data: {
      action: "HYBRID_TEST_START",
      status: "SUCCESS"
    }
  });
  console.log("Log enregistré dans Neon avec l'ID :", newLog.id);

  console.log("2. Vérification de la lecture sur Pinecone...");
  const index = pc.index(process.env.PINECONE_INDEX_NAME || "bek-memory");
  const stats = await index.describeIndexStats();
  console.log(`Mémoire vectorielle prête. Nombre total de vecteurs : ${stats.totalRecordCount}`);

  console.log("✨ Test hybride réussi avec succès ! Base relationnelle et mémoire vectorielle connectées.");
}

main()
  .catch((e) => {
    console.error("Erreur lors du test hybride :", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
    await pool.end();
  });