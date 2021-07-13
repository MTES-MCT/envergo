# This file contains hooks for the Scalingo deployment

# This is run at the end of the build process
# Scalingo will in fact run any `bin/post_compile` executable file it finds,
# so the following line is actually useless. It is kept for documentation purpose.
postcompile: bash bin/build_assets.sh

# This is the main process entrypoint
web: bash bin/start_web.sh

# This is run once at the end of the deployment, in a one-off container
postdeploy: bash bin/post_deploy.sh
