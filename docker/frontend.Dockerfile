FROM node:22-alpine

WORKDIR /app

COPY client/package.json client/package-lock.json ./

RUN npm ci

COPY client/ ./

EXPOSE 3000

CMD ["npm", "run", "dev"]