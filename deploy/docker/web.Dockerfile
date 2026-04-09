FROM node:20-alpine AS build-stage

WORKDIR /workspace/front

COPY front/agent_web_ui/package*.json ./
RUN npm ci --no-audit --no-fund

COPY front/agent_web_ui ./
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx/site.conf /etc/nginx/conf.d/default.conf
COPY --from=build-stage /workspace/front/dist /usr/share/nginx/html

EXPOSE 80
