FROM node:20-alpine AS builder

WORKDIR /app

COPY apps/web/ ./apps/web/
COPY packages/contracts/ ./packages/contracts/
COPY package.json ./

# Install and build Next.js
WORKDIR /app/apps/web
RUN npm install
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

COPY --from=builder /app/apps/web/.next ./apps/web/.next
COPY --from=builder /app/apps/web/package.json ./apps/web/
COPY --from=builder /app/apps/web/node_modules ./apps/web/node_modules

ENV NODE_ENV=production
ENV PORT=3000
ENV NEXT_PUBLIC_API_BASE_URL=http://api:4000
ENV NEXT_PUBLIC_WS_URL=ws://api:4000

EXPOSE 3000

WORKDIR /app/apps/web
CMD ["npm", "start"]
