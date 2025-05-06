# By Guilherme F Sampaio.

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload

from app.errors.errors import *

import os
import io
import logging
from abc import ABC, abstractmethod

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] - [%(levelname)s] - %(message)s"
)

logger = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


class GoogleDriveInterface(ABC):
    """
    Interface for interacting with Google Drive. Defines the necessary methods
    for authentication and obtaining the Google Drive service.
    """

    @abstractmethod
    def authenticate(self):
        """
        Abstract method to authenticate with Google Drive.
        """
        pass

    @abstractmethod
    def get_drive_service(self):
        """
        Abstract method to retrieve the authenticated Google Drive service.
        """
        pass


class GoogleDriveAuth(GoogleDriveInterface):
    """
    Google Drive authentication handler. Implements the GoogleDriveInterface
    to authenticate and obtain an authenticated Google Drive service.
    """

    def __init__(self, scopes):
        self.scopes = scopes
        self.drive_service = None

    def authenticate(self, local: bool = False):
        try:
            if local:
                service_account_file = os.path.join(
                    CURRENT_DIR, ".creds", "service_account.json"
                )
                creds = service_account.Credentials.from_service_account_file(
                    service_account_file, scopes=self.scopes
                )
            else:
                creds = service_account.Credentials.from_service_account_file(
                    "service_account.json", scopes=self.scopes
                )
            self.drive_service = build("drive", "v3", credentials=creds)
            logger.info("Google Drive service authenticated successfully.")
        except Exception as e:
            raise DriveAuthError(f"Error getting Google Drive credentials: {e}")

    def get_drive_service(self):
        if self.drive_service is None:
            raise DriveAuthError("Google Drive service is not authenticated.")
        return self.drive_service


class FileUploader:
    """
    Initializes the GoogleDriveAuth instance with the service account file path and scopes.
    """

    def __init__(self, service: GoogleDriveInterface):
        self.service = service.drive_service

    def get_file_by_name(self, file_name: str, folder_id: str):
        """Retrieves the file ID of a file in a specific folder on Google Drive by its name."""

        query = f"name='{file_name}' and '{folder_id}' in parents"
        results = self.service.files().list(q=query, fields="files(id)").execute()
        items = results.get("files", [])

        if items:
            if isinstance(items, list):
                if len(items) > 1:
                    raise ValueError(
                        f"Multiple files with the name {file_name} found in the folder with ID: {folder_id}."
                    )
                else:
                    return items[0]["id"]
            return items
        else:
            raise ValueError(
                f"{file_name} not found in the folder with ID: {folder_id}."
            )

    def upload(self, filepath: str, filename: str, folder_id: str):
        """Uploads a file to Google Drive. If the file already exists in the folder, it is updated."""
        try:
            query = f"name='{filename}' and '{folder_id}' in parents"
            results = self.service.files().list(q=query, fields="files(id)").execute()
            items = results.get("files", [])

            if items:
                file_id = items[0]["id"]
                media = MediaFileUpload(
                    filepath, mimetype="application/octet-stream"
                )

                file = (
                    self.service.files()
                    .update(fileId=file_id, media_body=media)
                    .execute()
                )
                logger.info(f'File {filename} updated with ID: {file.get("id")}')
            else:
                media = MediaFileUpload(
                    filepath, mimetype="application/octet-stream"
                )

                file_metadata = {
                    "name": filename,
                    "parents": [folder_id],
                }

                file = (
                    self.service.files()
                    .create(body=file_metadata, media_body=media)
                    .execute()
                )
                logger.info(f"File {filename} uploaded with ID: {file.get('id')}")
        except Exception as e:
            raise ValueError(f"{filename} not found in folder with ID: {folder_id}.")

    def download(self, file_name: str, folder_id: str, destination_path: str):
        """
        Downloads a file from Google Drive to a specified local path.
        """

        try:
            file_id = self.get_file_by_name(file_name, folder_id)
            request = self.service.files().get_media(fileId=file_id)

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()
                logger.info(f"Download {int(status.progress() * 100)}%.")

            with open(destination_path, "wb") as f:
                fh.seek(0)
                f.write(fh.read())

            logger.info(
                f"File {file_name} downloaded successfully to {destination_path}."
            )
        except ValueError as e:
            logger.error(f"Download error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during download: {str(e)}")
            raise
