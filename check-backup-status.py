import sys
import logging
from gcp_utils import get_compute_service_clients, get_instances, get_last_snapshot_date
from settings import project_id, backup_label_key, backup_label_value
from tabulate import tabulate

logging.basicConfig(level=logging.INFO, format='%(asctime)s    %(levelname)s    %(message)s')

def list_instances(zone):
    
    instances_client, snapshots_client = get_compute_service_clients()
    instances = get_instances(instances_client, zone)
    logging.info("Starting backup process")

    #I used tabulate because I'm familiar with it, would love to know what you used for your formatting though, looks great
    headers = ["Instance", "Backup Enabled", "Disk", "Latest Backup"]
    table = []

    for instance in instances:
        instance_name = instance.name
        first_disk_url = instance.disks[0].source if instance.disks else 'No disk attached'
        has_backup_label = instance.labels.get(backup_label_key) == backup_label_value
        backup_status = "Yes" if has_backup_label else "No"
        last_snapshot_date = get_last_snapshot_date(snapshots_client, first_disk_url) if first_disk_url != 'No disk attached' else 'No disk attached'
        last_snapshot_date = last_snapshot_date if last_snapshot_date is not None else 'No stored backup'
        row = [instance_name, backup_status, first_disk_url.split('/')[-1] if first_disk_url != 'No disk attached' else first_disk_url, last_snapshot_date]
        table.append(row)
    
    logging.info(f"Listing compute instances in {project_id} >> {zone}:")
    print(tabulate(table, headers, tablefmt="grid"))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please specify your zone - USAGE: python check-backup-status.py zone")
        sys.exit(1)

    zone = sys.argv[1]

    list_instances(zone)