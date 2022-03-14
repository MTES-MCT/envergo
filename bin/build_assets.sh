#!/bin/bash
# This script is ran by scalingo at the end of the build process

compress_enabled() {
python << END
import sys

from environ import Env

env = Env(COMPRESS_ENABLED=(bool, True))
if env('COMPRESS_ENABLED'):
    sys.exit(0)
else:
    sys.exit(1)

END
}

echo "Starting the post_compile hook"

npm run build
if compress_enabled
then
  python manage.py compress --force
fi
python manage.py collectstatic --noinput --clear
python manage.py compilemessages -l fr -i .scalingo -i .venv

echo "Leaving the post_compile hook"
