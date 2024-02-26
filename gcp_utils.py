from google.oauth2 import service_account
from google.cloud import compute_v1
from datetime import datetime, timedelta, timezone
from google.api_core.exceptions import GoogleAPICallError, RetryError, NotFound
from settings import project_id, path_to_credentials
from cardinality import count
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s   %(levelname)s   %(message)s')

def get_compute_service_clients():
    
    #Note: If deploying an app like this to a container/vm I would set environment variable GOOGLE_APPLICATION_CREDENTIALS on that machine to the credentials in the service-account file you provided. 
    #google.cloud.InstancesClient() could then be able to access them automatically. Because I'm running this on my local machine I'm going take the credentials directly from the service-account file instead.

    credentials = service_account.Credentials.from_service_account_file(
        path_to_credentials,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    instances_client = compute_v1.InstancesClient(credentials=credentials)
    snapshots_client = compute_v1.SnapshotsClient(credentials=credentials)

    return instances_client, snapshots_client

def get_instances(instances_client, zone):
    request = compute_v1.ListInstancesRequest(project=project_id, zone=zone)
    instances = instances_client.list(request=request)
    print(f"Found {count(instances)} instances")
    return instances

def check_snapshot_status(snapshots_client, snapshot_name):
    
    snapshot = snapshots_client.get(project=project_id, snapshot=snapshot_name)
    return snapshot.status

def check_snapshot_error(snapshots_client, snapshot_name):

    snapshot = snapshots_client.get(project=project_id, snapshot=snapshot_name)
    if snapshot.error:
        return snapshot.error.errors #sometimes snapshots will return multiple errors
    else: 
        return None

def get_last_snapshot_date(snapshots_client, disk_url):
    
    query = compute_v1.ListSnapshotsRequest(project=project_id)
    snapshots = snapshots_client.list(request=query)
    last_snapshot_date = None
    for snapshot in snapshots:
        if snapshot.source_disk == disk_url:
            snapshot_date = datetime.fromisoformat(snapshot.creation_timestamp.replace('Z', '+00:00'))
            if last_snapshot_date is None or snapshot_date > last_snapshot_date:
                last_snapshot_date = snapshot_date
    return last_snapshot_date

def get_invalid_snapshots(snapshots_client, disk_url):

    disk_name = disk_url.split('/')[-1]

    #I would prefer to use a filter param here but when I use request = compute_v1.ListSnapshotsRequest(project=project_id, filter=f'sourceDisk = {disk_name}')
    #I'm getting a 503 - Code: 6124A55B0E6DB.62507DB.DE00B541
    
    #For now I'm going to get around this by downloading them all and grouping in a dict
    snapshots_by_source_disk = {}
    
    request = compute_v1.ListSnapshotsRequest(project=project_id)
    for snapshot in snapshots_client.list(request=request):
        source_disk = snapshot.source_disk
        if source_disk not in snapshots_by_source_disk:
            snapshots_by_source_disk[source_disk] = []
        snapshots_by_source_disk[source_disk].append(snapshot)

    snapshots = snapshots_by_source_disk.get(disk_url, False)

    if not snapshots:
        logging.info(f"No snapshots of {disk_name} found.")
        return False

    logging.info(f"{len(snapshots)} snapshot(s) of {disk_name} found.")
    snapshots = sorted(snapshots, key=lambda x: x.creation_timestamp)  
    
    snapshots_by_day = []
    snapshots_by_week = []

    for snapshot in snapshots:
        
        current_datetime = datetime.now(timezone.utc)
        snapshot_datetime = datetime.fromisoformat(snapshot.creation_timestamp.replace('Z', '+00:00'))
        
        if (current_datetime - snapshot_datetime) <= timedelta(days=7):
            iso_day = snapshot_datetime.isocalendar().weekday
            snapshots_by_day.append((snapshot.name, snapshot_datetime, iso_day))
        
        elif (current_datetime - snapshot_datetime) > timedelta(days=7):           
            iso_week = snapshot_datetime.isocalendar().week
            snapshots_by_week.append((snapshot.name, snapshot_datetime, iso_week))

    valid_snapshots_daily = {t[2]: t for t in snapshots_by_day}
    valid_snapshots_weekly = {t[2]: t for t in snapshots_by_week}
    valid_snapshots = [t[0] for t in valid_snapshots_daily.values()] + [t[0] for t in valid_snapshots_weekly.values()]

    invalid = [snapshot for snapshot in snapshots if snapshot.name not in valid_snapshots]

    return invalid

def create_snapshot(snapshots_client, zone, instance, disk_name, disk_url):

    request_time = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    snapshot = compute_v1.Snapshot()
    snapshot.name = f"{disk_name}-snapshot-{request_time}"
    snapshot.description = f"Automated backup snapshot requested at {request_time}"
    snapshot.source_disk = disk_url
    
    try:
        snapshots_client.insert(project=project_id, snapshot_resource=snapshot)
        logging.info(f"Requested snapshot creation for {project_id} >> {zone} >> {instance.name} >> {disk_name}")
    except (GoogleAPICallError, RetryError) as e:
        logging.error(f"Failed to create snapshot: {snapshot.name}: {e}")

    #There are a number of ways you can do this - Google recommends using google.api_core.extended_operation's operation.result() for async await
    #I would tend to use a GlobalOperationsClient to check status but I don't have the permissions to do so with these credentials
    
    while True:
        status = check_snapshot_status(snapshots_client, snapshot.name)
        match status:
            case 'CREATING':
                logging.info(f"Snapshot {snapshot.name} is being created...")
            case 'UPLOADING':
                logging.info(f"Snapshot {snapshot.name} is being uploaded...")
            case 'READY':
                logging.info(f"Instance: {instance.name} Disk: {disk_name} has been backed up into snapshot: {snapshot.name}")
                return
            case 'FAILED':
                logging.error(f"Snapshot {snapshot.name} failed.")
                errors = check_snapshot_error(snapshots_client, project_id, snapshot.name)
                for error in errors:
                    logging.error(f"{error}")
        time.sleep(4)
        
def remove_snapshot(snapshot_client, snapshot_name):
    #The logic around deciding if a snapshot has been deleted successfully here is a bit imprecise. I would prefer
    #to use an operations client here to observe the deletion operation rather than just polling for if the resource
    #can be found. Iirc 'DELETED' is a valid case, but I'm not sure how long it actually lasts for or how to access
    #a snapshot in that state.
    logging.info(f"Deleting snapshot {snapshot_name}...")
    try:
        snapshot_client.delete(project=project_id, snapshot=snapshot_name)
    except (GoogleAPICallError, RetryError) as e:
        logging.error(f"Snapshot deletion for {snapshot_name} failed.")
        logging.error(f"{e}")

    while True:
        try:
            status = check_snapshot_status(snapshot_client, snapshot_name)
            match status:
                case 'DELETING':
                    logging.info("Snapshot is being deleted...")
                case 'DELETED':
                    logging.info("Snapshot deleted.")
                    break
        except NotFound: 
            logging.info(f"Snapshot {snapshot_name} deleted.")
            break  
        time.sleep(2)
