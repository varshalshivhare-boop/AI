FROM node:20-alpine

WORKDIR /app

# Copy only the files this service needs
COPY services/market-data/replayer.ts ./services/market-data/
COPY packages/contracts/src/ ./packages/contracts/src/
COPY fixtures/ ./fixtures/
COPY package.json ./

ENV NODE_ENV=production
ENV DATA_MODE=REPLAY

CMD ["node", "--input-type=module", "services/market-data/replayer.ts"]
