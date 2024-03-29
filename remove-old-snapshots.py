import sys
import logging
import threading
from gcp_utils import get_compute_service_clients, get_instances, get_invalid_snapshots, remove_snapshot

logging.basicConfig(level=logging.INFO, format='%(asctime)s    %(levelname)s    %(message)s')

def remove_old_snapshots(zone):
    
    logging.info("Starting backup removal process...")
    instances_client, snapshots_client = get_compute_service_clients()
    
    instances = get_instances(instances_client, zone)
    
    for instance in instances:
        logging.info(f"Instance: {instance.name}")
        first_disk_url = instance.disks[0].source if instance.disks else None
        first_disk_name = first_disk_url.split('/')[-1] if first_disk_url else None
        if first_disk_url:
            out_of_date_snapshots = get_invalid_snapshots(snapshots_client, first_disk_url)
            if out_of_date_snapshots:
                logging.info(f"{instance.name} >> {first_disk_name} has snapshots outside of retention policy.")
                for snapshot in out_of_date_snapshots:
                    deletion_thread = threading.Thread(target=remove_snapshot, args=(snapshots_client, snapshot.name))
                    deletion_thread.start()
            else:
                logging.info(f"Found no snapshots outside retention policy for {instance.name} >> {first_disk_name}.")
        else:
            logging.info(f"No disk attached to {instance.name}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Please specify your zone - USAGE: python backup-virtual-machines.py zone")
        sys.exit(1)

    zone = sys.argv[1]
    remove_old_snapshots(zone)