# Multi-stage production build using light alpine image

# Stage 1: Dependencies build
FROM node:18-alpine AS builder
WORKDIR /usr/src/app

COPY package*.json ./
RUN npm ci --omit=dev

# Stage 2: Production runtime image
FROM node:18-alpine AS runner
WORKDIR /usr/src/app

ENV NODE_ENV=production
ENV PORT=3000

# Copy installed production node_modules and code from builder stage
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY package*.json ./
COPY server.js cpu-worker.js ./

# Run container as standard non-root node user for security
USER node

EXPOSE 3000

CMD ["node", "server.js"]
