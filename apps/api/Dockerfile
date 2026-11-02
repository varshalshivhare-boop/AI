FROM node:20-alpine

WORKDIR /app

COPY apps/api/ ./apps/api/
COPY packages/contracts/ ./packages/contracts/
COPY fixtures/ ./fixtures/
COPY package.json ./

ENV NODE_ENV=production
ENV PORT=4000
ENV DATA_MODE=DEMO

EXPOSE 4000

CMD ["node", "apps/api/src/mock-server.ts"]
