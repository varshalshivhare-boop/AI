FROM node:20-alpine

WORKDIR /app

COPY services/quant-engine/engine.ts ./services/quant-engine/
COPY packages/contracts/src/ ./packages/contracts/src/
COPY package.json ./

ENV NODE_ENV=production

CMD ["node", "--input-type=module", "services/quant-engine/engine.ts"]
