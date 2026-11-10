import argparse

from sqlalchemy import select

from app.database import SessionLocal
from app.models.user import User
from app.security import create_password_setup_token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a short-lived password setup token for a verified legacy account."
    )
    parser.add_argument("user_id", type=int)
    args = parser.parse_args()

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.id == args.user_id))
        if user is None:
            parser.error("No user exists with that ID")
        if user.password_hash is not None:
            parser.error("This account already has a password")
        token = create_password_setup_token(user.id)

    print(token)


if __name__ == "__main__":
    main()