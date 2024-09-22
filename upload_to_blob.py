import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import os

load_dotenv()

connection_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
container_name = os.getenv("BLOB_STORAGE_CONTAINER_NAME")
local_folder = "resources/azure-blob-storage"

blob_service_client = BlobServiceClient.from_connection_string(connection_str)
container_client = blob_service_client.get_container_client(container_name)

try:
    container_client.create_container()
except Exception as e:
    print(e)

def upload_files(folder_path, container_client):
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            if file_name.lower().endswith(".pdf"):
                local_file_path = os.path.join(root, file_name)
                
                relative_path = os.path.relpath(local_file_path, folder_path)
                blob_path = relative_path.replace("\\", "/") 
                
                print(f"Uploading {local_file_path} to {container_name}/{blob_path}...")
                blob_client = container_client.get_blob_client(blob_path)
                with open(local_file_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)
            else:
                print(f"Skipping: {file_name}")

upload_files(local_folder, container_client)

print("Finished uploading")

account_url = os.getenv("BLOB_ACCOUNT_URL")
default_credential = os.getenv("BLOB_ACCOUNT_CREDENTIALS")
container_name = os.getenv("BLOB_CONTAINER")

blob_service_client = BlobServiceClient(account_url, credential=default_credential)
container_client = blob_service_client.get_container_client(container_name)

blobs = container_client.list_blobs()

for blob in blobs:
    blob_path_parts = blob.name.split('/')
    
    if len(blob_path_parts) == 3:  
        team = blob_path_parts[0].replace('-team', '')
        member_name = blob_path_parts[1]
        pdf_name = blob_path_parts[2]

        if '_with' in pdf_name:
            kind_of = pdf_name.split('_with')[0]  
            kind_of = kind_of.replace('_', ' ')  
        elif '_' in pdf_name:
            kind_of = pdf_name.replace('_', ' ')  
        else:
            kind_of = 'horizontal'  

        print(f"Processing: {blob.name}")
        print(f"  Team: {team}")
        print(f"  Member: {member_name}")
        print(f"  Kind of: {kind_of}")
        
        blob_client = container_client.get_blob_client(blob.name)

        metadata = {
            "team": team,
            "member": member_name,
            "kind_of": kind_of
        }

        blob_client.set_blob_metadata(metadata)
        print(f"  Metadata added: {metadata}")
    else:
        print(f"Skipping blob: {blob.name}")

print("Finished setting metadata")
        
