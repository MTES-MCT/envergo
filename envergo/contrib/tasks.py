import logging
import subprocess

from config.celery_app import app

logger = logging.getLogger(__name__)


@app.task
def execute_s3_backup():
    """Asynchronously execute the backup of all the files in the s3 bucket to a cold storage."""
    logger.info(
        "Executing the backup of all the files in the s3 bucket to a cold storage."
    )
    subprocess.run(["bash", "bin/backup_s3_bucket.sh"], check=True)
