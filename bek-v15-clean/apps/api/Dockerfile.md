# ============================================
# Dockerfile API NestJS
# Chemin : E:\\crm-release\\apps\\api\\Dockerfile
# ============================================

FROM oven/bun:1-slim AS builder
WORKDIR /app

# 1. Dépendances
COPY package.json ./
COPY apps/api/package.json ./apps/api/
COPY packages/db/package.json ./packages/db/
COPY packages/env/package.json ./packages/env/

RUN bun install

# 2. Code source
COPY . .

# 3. Prisma Client
RUN cd packages/db && bunx prisma generate --schema=prisma/schema.prisma

# 4. Build NestJS
RUN cd apps/api && bun run build

# ============================================
# Runtime
# ============================================
FROM oven/bun:1-slim
WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/packages ./packages
COPY --from=builder /app/apps/api/dist ./apps/api/dist
COPY --from=builder /app/apps/api/package.json ./apps/api/

ENV PORT=3001
ENV NODE_ENV=production
EXPOSE 3001

CMD ["bun", "run", "apps/api/dist/main.js"]
