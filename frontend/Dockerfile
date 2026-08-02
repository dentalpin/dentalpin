# Build stage
FROM node:22-alpine AS builder

WORKDIR /app
ARG API_BASE_URL=http://localhost:8000
ENV API_BASE_URL=$API_BASE_URL

# Copy package files from the frontend directory
COPY frontend/package*.json ./
RUN npm install

# Copy the entire modules tree so Nuxt can discover them at build time
COPY backend/app/modules /module_layers

# Copy the frontend source code
COPY frontend/ .

ENV NODE_OPTIONS=--max-old-space-size=4096

RUN npm run build
# Production stage
FROM node:22-alpine

WORKDIR /app

# Copy built output
COPY --from=builder /app/.output /app/.output

# Set environment variables
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

EXPOSE 3000

# Start the application
CMD ["node", ".output/server/index.mjs"]
