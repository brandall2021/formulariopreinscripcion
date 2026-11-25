FROM node:22-alpine AS build
WORKDIR /src
COPY package*.json ./
RUN npm ci
COPY . .
ARG API_URL=http://localhost:8000
RUN printf 'export const environment = { apiUrl: "%s" };\n' "$API_URL" > src/environments/environment.ts \
 && npm run build
FROM nginx:1.27-alpine
COPY --from=build /src/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
