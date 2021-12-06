from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

def google_drive_auth():
    auth = GoogleAuth()
    auth.LocalWebserverAuth()

    return auth


def get_shows_csv(drive: GoogleDrive = None):
    if drive is None:
        auth = google_drive_auth()
        drive = GoogleDrive(auth)

    file_list = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
    for file in file_list:
        if file['title'] == "shows.csv":
            print("Found File shows.csv")
            file.GetContentFile(file['title'])


if __name__ == '__main__':
    auth = google_drive_auth()
    drive = GoogleDrive(auth)
    get_shows_csv(drive)
