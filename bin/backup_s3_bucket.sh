#!/bin/bash
# This script is ran by scalingo at the end of the build process

# Interrupt script on error
set -e

echo "Starting the backup of s3 bucket"

# TODO uncomment this block when feature is ready
#if [ "$IS_REVIEW_APP" = True ]; then
#  echo "Backup is not enabled for this environment"
#  exit 0
#fi

if ! ls rclone-*-linux-amd64 | grep rclone >/dev/null; then
  echo "Installing rclone"
  apt-get update && apt-get install -y curl unzip
  curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip
  unzip rclone-current-linux-amd64.zip
fi

echo "Performing backup"
cd rclone-*-linux-amd64
# TODO use the real prod bucket
./rclone sync -vvv --s3-storage-class=GLACIER :s3,provider=Scaleway,region=fr-par,endpoint=s3.fr-par.scw.cloud,access_key_id=$SCALEWAY_ACCESS_KEY,secret_access_key=$SCALEWAY_SECRET_KEY:envergo-prod  :s3,provider=Scaleway,region=nl-ams,endpoint=s3.nl-ams.scw.cloud,access_key_id=$SCALEWAY_ACCESS_KEY,secret_access_key=$SCALEWAY_SECRET_KEY:envergo-prod-backup


echo "Leaving the s3 backup script"
