import sys
from google.cloud import compute_v1
from gcp_utils import get_compute_service_clients, get_instances, get_last_snapshot_date
from datetime import datetime, timedelta, timezone
from tabulate import tabulate

#I hardcoded these parameters but you could expose them with options on __main__ or poll the user with the terminal if you wanted to be able to use multiple projects, change label_key, etc.
def list_instances(zone, project_id='xcc-tadgh-gcp', label_key='backup', label_value='true'):
    
    path_to_credentials = "credentials/xcc-tadgh-gcp.json"
    instances_client, snapshots_client = get_compute_service_clients(path_to_credentials)
    instances = get_instances(instances_client, project_id, zone)

    #I used tabulate because I'm familiar with it, would love to know what you used for your formatting though, looks great
    headers = ["Instance", "Backup Enabled", "Disk", "Latest Backup"]
    table = []

    for instance in instances:
        instance_name = instance.name
        first_disk_url = instance.disks[0].source if instance.disks else 'No disk attached'
        has_backup_label = instance.labels.get(label_key) == label_value
        backup_status = "Yes" if has_backup_label else "No"
        last_snapshot_date = get_last_snapshot_date(snapshots_client, project_id, first_disk_url) if first_disk_url != 'No disk attached' else 'No disk attached'
        last_snapshot_date = last_snapshot_date if last_snapshot_date is not None else 'No backup found'
        row = [instance_name, backup_status, first_disk_url.split('/')[-1] if first_disk_url != 'No disk attached' else first_disk_url, last_snapshot_date]
        table.append(row)
    
    print(f"{datetime.now(timezone.utc)} INFO - Listing compute instances in {project_id}, {zone}:")
    print(tabulate(table, headers, tablefmt="grid"))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please specify your zone - USAGE: python check-backup-status.py zone")
        sys.exit(1)

    zone = sys.argv[1]

    list_instances(zone)