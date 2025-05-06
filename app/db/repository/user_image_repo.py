from sqlalchemy.orm import Session

from app.db.entities.user_image import UserImages

class UserImageRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_checked_image_urls(self):
        return [
            row.image_url
            for row in self.session.query(UserImages)
            .filter(UserImages.checked == 0)
            .all()
        ]

    def apply_checked_image_urls(self, image_urls):
        if not image_urls:
            return

        self.session.query(UserImages)\
            .filter(UserImages.image_url.in_(image_urls))\
            .update({UserImages.checked: 1}, synchronize_session='fetch')

        self.session.commit()

    def remove_urls_with_errors(self, image_urls):
        if not image_urls:
            return

        self.session.query(UserImages)\
            .filter(UserImages.image_url.in_(image_urls))\
            .delete(synchronize_session=False)

        self.session.commit()