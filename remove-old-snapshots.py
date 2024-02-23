import sys
from google.cloud import compute_v1
from datetime import datetime, timezone
from gcp_utils import get_compute_service_clients, get_out_of_date_snapshots, remove_snapshot_blocking
import cardinality

def remove_old_snapshots(zone, project_id='xcc-tadgh-gcp'):
    
    print(f"{datetime.now(timezone.utc)} INFO - Starting backup process...")
    path_to_credentials = "credentials/xcc-tadgh-gcp.json"
    instances_client, snapshots_client = get_compute_service_clients(path_to_credentials)
    
    request = compute_v1.ListInstancesRequest(project=project_id, zone=zone)
    instances = instances_client.list(request=request)
    print(f"{datetime.now(timezone.utc)} INFO - Found {cardinality.count(instances)} instances in {project_id} >> {zone}.")

    for instance in instances:
        first_disk_url = instance.disks[0].source if instance.disks else None
        first_disk_name = first_disk_url.split('/')[-1] if first_disk_url else None
        if first_disk_url:
            out_of_date_snapshots = get_out_of_date_snapshots(snapshots_client, project_id, first_disk_url)
            if out_of_date_snapshots:
                print(f"{datetime.now(timezone.utc)} INFO - Instance: {instance.name} >> Disk: {first_disk_name} has out of date snapshots.")
                for snapshot in out_of_date_snapshots:
                    remove_snapshot_blocking(snapshots_client, project_id, snapshot.name)
            else:
                print(f"{datetime.now(timezone.utc)} INFO - Found no out-of-date snapshots for {instance.name} >> {first_disk_name}.")
        else:
            print(f"{datetime.now(timezone.utc)} INFO - No disk attached to {instance.name} >> {first_disk_name}.")


    print(f"{datetime.now(timezone.utc)} INFO - All instances in {project_id} >> {zone} have had their old backups removed")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please specify your zone - USAGE: python backup-virtual-machines.py zone")
        sys.exit(1)

    zone = sys.argv[1]
    remove_old_snapshots(zone)