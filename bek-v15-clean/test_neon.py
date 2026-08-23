 
cat << 'EOF' > test_neon.py
import psycopg2
import sys

# Collez votre DATABASE_URL exacte ci-dessous si différente
DATABASE_URL = "VOTRE_DATABASE_URL_ICI"

try:
    print("Connexion à Neon en cours...")
    conn = psycopg2.connect(DATABASE_URL=postgresql://neondb_owner:npg_FqRIu3UOyPJ8@ep-misty-dream-ay7lX9lc.
c-5.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
)
    cur = conn.cursor()
    
    # 1. Vérifier la connexion
    cur.execute("SELECT current_database(), version();")
    db_name, version = cur.fetchone()
    print(f" Connecté à la base : {db_name}")
    
    # 2. Lister les tables créées par Prisma
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    
    print("\n Tables existantes dans le CRM Neon :")
    for t in tables:
        print(f"  - {t[0]}")
        
    cur.close()
    conn.close()
    print("\n Test réussi sans surcharge CPU !")

except Exception as e:
    print(f" Erreur : {e}")
    sys.exit(1)
EOF