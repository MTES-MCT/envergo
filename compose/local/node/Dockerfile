FROM node:14-buster-slim

WORKDIR /app

COPY ./src/package.json /app
COPY ./src/package-lock.json /app

RUN npm install && npm cache clean --force

ENV PATH ./node_modules/.bin/:$PATH
