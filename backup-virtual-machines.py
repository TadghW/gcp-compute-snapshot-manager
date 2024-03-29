import sys
import logging
import threading
from gcp_utils import get_compute_service_clients, get_instances, get_last_snapshot_date, create_snapshot
from settings import project_id, backup_label_key, backup_label_value
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s    %(levelname)s    %(message)s')

def backup_instances(zone):
    
    logging.info("Starting backup process...")
    instances_client, snapshots_client = get_compute_service_clients()
    instances = get_instances(instances_client, zone)

    for instance in instances:
        logging.info(f"Instance: {instance.name}")
        if instance.labels.get(backup_label_key) == backup_label_value:
            logging.info("Backup Enabled: True")
            first_disk_url = instance.disks[0].source if instance.disks else None
            first_disk_name = first_disk_url.split('/')[-1] if first_disk_url else None
            if first_disk_url:
                last_snapshot_date = get_last_snapshot_date(snapshots_client, first_disk_url)
                logging.info(f"Last snapshot was at {last_snapshot_date}.")
                if not last_snapshot_date or (datetime.now(timezone.utc) - last_snapshot_date) > timedelta(days=1):
                    creation_thread = threading.Thread(target=create_snapshot, args=(snapshots_client, zone, instance, first_disk_name, first_disk_url))
                    creation_thread.start()
                else:
                    logging.info("Skipping backup creation")
            else:
                logging.info(f"No disk attached to {instance.name}")
        else:
            logging.info("Backup Enabled: False")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please specify your zone - USAGE: python backup-virtual-machines.py zone")
        sys.exit(1)

    zone = sys.argv[1]
    backup_instances(zone)