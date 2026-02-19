FROM docker.io/python:3.12.8-slim-bookworm as python

# Python build stage
FROM python as python-build-stage

ARG BUILD_ENVIRONMENT=local

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential

# build assets
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
  && apt-get install -y nodejs
# Requirements are installed here to ensure they will be cached.
COPY ./requirements .

# Create Python Dependency and Sub-Dependency Wheels.
RUN python -m ensurepip --upgrade && pip wheel --wheel-dir /usr/src/app/wheels  \
  -r ${BUILD_ENVIRONMENT}.txt


# Python 'run' stage
FROM python as python-run-stage

ARG BUILD_ENVIRONMENT=local
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV BUILD_ENV ${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg2 dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  # localisation dependencies \
  locales locales-all \
  # Geo tools
  binutils libproj-dev libheif1 gdal-bin \
  curl \
  # python-magic mimetype detection dependencies
  libmagic1 \
  # cleaning up unused files
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
  && apt-get install -y nodejs

RUN locale-gen fr_FR.UTF-8 && update-locale LANG="fr_FR.UTF-8" LC_ALL="fr_FR.UTF-8"

ENV LANG fr_FR.UTF-8
ENV LC_ALL fr_FR.UTF-8

# All absolute dir copies ignore workdir instruction. All relative dir copies are wrt to the workdir instruction
# copy python dependency wheels from python-build-stage
COPY --from=python-build-stage /usr/src/app/wheels  /wheels/

# use wheels to install python dependencies
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
	&& rm -rf /wheels/

COPY ./compose/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start


# copy application code to WORKDIR
COPY . ${APP_HOME}

# This is required because we disabled all npm scripts in .npmrc
RUN node node_modules/optipng-bin/lib/install.js

ENTRYPOINT ["/entrypoint"]
