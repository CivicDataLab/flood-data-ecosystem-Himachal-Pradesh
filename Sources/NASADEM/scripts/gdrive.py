import os

from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

cwd = os.getcwd()

service_account = "<service_account>"  # Add service account.
# authenticate to Google Drive (of the Service account)
gauth = GoogleAuth()
scopes = ["https://www.googleapis.com/auth/drive"]
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(
    f"{cwd}/<secret.env>", scopes=scopes
)
drive = GoogleDrive(gauth)

# To get folder ID
# file_list = drive.ListFile().GetList()
# print(file_list)
# for file in file_list:
#     print(file["title"], file["id"])

NASADEM_folder_id = "1NfiKDY3JaOCrL2vRgZOojefhzwTLP8gW"

# get list of files
file_list = drive.ListFile(
    {"q": "'{}' in parents and trashed=false".format(NASADEM_folder_id)}
).GetList()
# print(file_list)

if file_list:
    for file in file_list:
        filename = file["title"]
        print(file["title"], file["mimeType"])

        # download file into working directory (in this case a tiff-file)
        file.GetContentFile(
            cwd + "/Sources/NASADEM/data/" + filename, mimetype=file["mimeType"]
        )

        # delete file afterwards to keep the Drive empty
        file.Delete()
else:
    print("No Files Found!!")
