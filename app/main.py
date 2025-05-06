import logging
from pathlib import Path

import requests
from dotenv import load_dotenv

from app.services.google_drive import GoogleDriveAuth, FileUploader
from app.db.config.db_config import DBConnectionHandler
from app.db.repository.user_image_repo import UserImageRepository
from app.settings.creds import GDRIVE_FOLDER_ID, IMAGES_GDRIVE_FOLDER_ID

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).resolve().parent
DB_FILENAME = "user_images.db"
DB_FILE_PATH = CURRENT_DIR / "data" / DB_FILENAME


def download_images(image_urls, download_dir: Path):
    """Baixa imagens para o diretório especificado."""
    logger.info(f"Baixando imagens para {download_dir}")
    urls_with_errors = []

    for url in image_urls:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            file_path = download_dir / Path(url).name
            file_path.write_bytes(response.content)
            logger.info(f"Imagem salva: {file_path}")
        except Exception as e:
            logger.error(f"Erro ao baixar {url}: {e}")
            urls_with_errors.append(url)

    logger.info(f"Todas as imagens foram processadas em {download_dir}")
    return urls_with_errors


def upload_images_to_gdrive(upload_dir: Path, uploader: FileUploader):
    """Envia arquivos do diretório para o Google Drive."""
    for file_path in upload_dir.iterdir():
        if file_path.is_file():
            filename = file_path.name
            uploader.upload(str(file_path), filename, IMAGES_GDRIVE_FOLDER_ID)
            logger.info(f"Arquivo enviado para o Google Drive: {file_path}")


def main():
    gdrive_auth = GoogleDriveAuth(scopes=["https://www.googleapis.com/auth/drive"])
    gdrive_auth.authenticate(local=False)
    uploader = FileUploader(gdrive_auth)
    uploader.download(
        DB_FILENAME, GDRIVE_FOLDER_ID, str(DB_FILE_PATH)
    )  # <-- Download the database file

    with DBConnectionHandler() as session:
        repo = UserImageRepository(session)
        image_urls = repo.get_checked_image_urls()
        logger.info(f"Total de URLs de imagem: {len(image_urls)}")

        if not image_urls:
            logger.info("Nenhuma imagem para processar.")
            return

        TMP_DIR = CURRENT_DIR / "tmp"
        TMP_DIR.mkdir(exist_ok=True)

        try:
            urls_with_erros = download_images(image_urls, TMP_DIR)
            logger.info("Iniciando o upload das imagens para o Google Drive...")
            upload_images_to_gdrive(TMP_DIR, uploader)
            logger.info("Upload concluído.")
            logger.info("Atualizando o banco de dados com as URLs verificadas...")
            repo.apply_checked_image_urls(image_urls)
            logger.info("URLs verificadas aplicadas com sucesso.")
            logger.info("Removendo URLs com erros do banco de dados...")
            repo.remove_urls_with_errors(urls_with_erros)
            logger.info("URLs com erros removidas com sucesso.")
        finally:
            for file in TMP_DIR.iterdir():
                if file.is_file():
                    file.unlink()

        uploader.upload(
            str(DB_FILE_PATH), DB_FILENAME, GDRIVE_FOLDER_ID
        )  # --> Upload the database file

    logger.info("Processo concluído com sucesso.")


if __name__ == "__main__":
    main()
