FROM node:20-alpine

WORKDIR /app/apps/web
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install
COPY apps/web ./
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
