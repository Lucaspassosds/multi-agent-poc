# Frontend image: Node 24 running the Vite dev server (HMR).
FROM node:24-slim

WORKDIR /app

# Install deps first for better layer caching. (No lockfile yet → npm creates one.)
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
