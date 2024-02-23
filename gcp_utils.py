from google.oauth2 import service_account
from google.cloud import compute_v1
from datetime import datetime, timedelta, timezone
from google.api_core.exceptions import GoogleAPICallError, RetryError, NotFound
from settings import project_id, path_to_credentials
import time
import cardinality

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
    print(f"{datetime.now(timezone.utc)} INFO - Found {cardinality.count(instances)} instances in {project_id} >> {zone}.")
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

def get_out_of_date_snapshots(snapshots_client, disk_url):

    query = compute_v1.ListSnapshotsRequest(project=project_id)
    snapshots = snapshots_client.list(request=query)
    out_of_date = []
    for snapshot in snapshots:
        if snapshot.source_disk == disk_url:
            snapshot_date = datetime.fromisoformat(snapshot.creation_timestamp.replace('Z', '+00:00'))
            if (datetime.now(timezone.utc) - snapshot_date) > timedelta(seconds=1): ##CHANGE TO DAYS BEFORE SUBMISSION
                out_of_date.append(snapshot)
    return out_of_date

def create_snapshot_blocking(snapshots_client, zone, instance, disk_name, disk_url):

    request_time = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    snapshot = compute_v1.Snapshot()
    snapshot.name = f"{disk_name}-snapshot-{request_time}"
    snapshot.description = f"Automated backup snapshot requested at {request_time}"
    snapshot.source_disk = disk_url
    
    try:
        snapshots_client.insert(project=project_id, snapshot_resource=snapshot)
        print(f"{datetime.now(timezone.utc)} INFO - Requested snapshot creation for {project_id} >> {zone} >> {instance.name} >> {disk_name}")

        #There are a number of ways you can do this - Google recommends using google.api_core.extended_operation's operation.result() for async await
        #I would tend to use a GlobalOperationsClient to check status but I don't have the permissions to do so with these credentials
        while True:
            status = check_snapshot_status(snapshots_client, project_id, snapshot.name)
            match status:
                case 'CREATING':
                    print(f"{datetime.now(timezone.utc)} INFO - Snapshot is being created...")
                case 'UPLOADING':
                    print(f"{datetime.now(timezone.utc)} INFO - Snapshot is being uploaded...")
                case 'READY':
                    print(f"{datetime.now(timezone.utc)} SUCCESS - Snapshot created.")
                    return
                case 'FAILED':
                    print(f"{datetime.now(timezone.utc)} FAILED - Snapshot creation failed.")
                    errors = check_snapshot_error(snapshots_client, project_id, snapshot.name)
                    for error in errors:
                        print(f"{datetime.now(timezone.utc)} ERROR MESSAGE - {error}")
            time.sleep(4)
    except (GoogleAPICallError, RetryError) as e:
            print(f"{datetime.now(timezone.utc)} ERROR - Failed to create snapshot: {snapshot.name}: {e}")

def remove_snapshot_blocking(snapshot_client, snapshot_name):
    #The logic around deciding if a snapshot has been deleted successfully here is a bit imprecise. I would prefer
    #to use an operations client here to observe the deletion operation rather than just polling for if the resource
    #can be found. Iirc 'DELETED' is a valid case, but I'm not sure how long it actually lasts for or how to access
    #a snapshot in that state.
    print(f"{datetime.now(timezone.utc)} INFO - Deleting snapshot {snapshot_name}...")
    try:
        snapshot_client.delete(project=project_id, snapshot=snapshot_name)
        while True:
            try:
                status = check_snapshot_status(snapshot_client, project_id, snapshot_name)
                match status:
                    case 'DELETING':
                        print(f"{datetime.now(timezone.utc)} INFO - Snapshot is being deleted...")
                    case 'DELETED':
                        print(f"{datetime.now(timezone.utc)} SUCCESS - Snapshot deleted.")
                        break
            except NotFound: 
                print(f"{datetime.now(timezone.utc)} SUCCESS - Snapshot {snapshot_name} deleted.")
                break  
            time.sleep(2)
    except (GoogleAPICallError, RetryError) as e:
        print(f"{datetime.now(timezone.utc)} ERROR - Snapshot deletion for {snapshot_name} failed.")
        print(f"{datetime.now(timezone.utc)} ERROR MESSAGE - {e}.")