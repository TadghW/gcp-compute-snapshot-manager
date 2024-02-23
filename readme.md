### GCP Compute Snapshot Manager
This application enables the management of GCP Compute snapshots from the command line using Google's Comptue Engine for Python library. It demonstrates the enumeration of instances, persistent disks, and snapshots as well as how to interface with your project's snapshots via Compute's SnapshotsClient entity. 

Typically you might want to deploy this logic in the cloud so you could run the backup and backup-removal functionalities as chron jobs on a vm. In this case I've packaged this functionality so you can run it on a local computer.

 #### To test this application you will need:
 - Python 3 12.2 (with venv and pip)
 - At least one Google Cloud Compute project that has at least instance with a persistent disk
 - Valid credentials to access your Compute project stored as JSON, stored in a folder at the root of the project called 'credentials'

#### Setup:

 - **Clone the repository** with `git clone https://github.com/TadghW/gcp-compute-manager.git`
 - **Create a virtual environment** at the root of the cloned folder `python -m venv env_name` OR `python3 -m venv env_name` depending on your operating system and python installation
 - **Activate the virtual environment**. 
	 - On macOS and Linux you can use `source env_name/bin/activate`
	 - On Windows you can use `.\env_name/Scripts/activate.bat` if you're using the command prompt or terminal, or `.\env_name/Scripts/activate.ps1` if you're using a PowerShell terminal.
- **Install the project requirements** in the virtual environment using `pip install -r requirements.txt`
- **Store your user credentials** JSON in a folder at the project's root
- **Update the settings in `settings.py`** to reflect your own credentials file, project id, and backup label key and value