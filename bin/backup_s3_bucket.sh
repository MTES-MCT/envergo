#!/bin/bash
# This script is ran by scalingo scheduler every monday

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
# Get the arguments
scaleway_access_key=$1
scaleway_secret_key=$2

cd rclone-*-linux-amd64
./rclone sync -vvv --s3-storage-class=GLACIER :s3,provider=Scaleway,region=fr-par,endpoint=s3.fr-par.scw.cloud,access_key_id=$scaleway_access_key,secret_access_key=$scaleway_secret_key:envergo-stage/envergo-upload-prod :s3,provider=Scaleway,region=nl-ams,endpoint=s3.nl-ams.scw.cloud,access_key_id=$scaleway_access_key,secret_access_key=$scaleway_secret_key:envergo-prod-backup


echo "Leaving the s3 backup script"
