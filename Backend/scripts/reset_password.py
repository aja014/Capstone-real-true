"""System administrator reset (last resort): sets a new password and a new recovery code for ANY
account (Manager included), for when nobody has a working recovery code.

Run on the server, from Backend/, with the database in the environment (DATABASE_URL, as for the app):
    ./venv/Scripts/python scripts/reset_password.py
It asks for the username, then the new password twice (hidden, never as an argument), applies the
password rule, saves both and prints the new recovery code ONCE. Give the password and the code to
the user in person; they must set a new password of their own at the next login (must_change_password).
Nothing secret is logged; account_events gets a code_changed row (actor "system administrator"), so
the user sees the "Not you?" notice at the next login."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, engine  # noqa: E402
from app.security import hash_password, password_rule_error  # noqa: E402
from app.services import recovery  # noqa: E402
from app.services.user_service import get_user_by_username  # noqa: E402

ACTOR = "system administrator"


def main(ask=input, ask_secret=getpass.getpass, out=print, session_factory=SessionLocal):
    out(f"FIREMAP password reset - database: {engine.url.database}")
    db = session_factory()
    try:
        user = get_user_by_username(db, ask("Username: "))
        if user is None:
            out("No account with that username. Nothing changed.")
            return 1
        role = "Manager" if user.role == "manager" else "Admin & Finance"
        if ask(f"Reset the password of {user.username} ({role})? Type yes to continue: ").strip().lower() != "yes":
            out("Cancelled. Nothing changed.")
            return 1

        password = ask_secret("New password: ")
        rule_error = password_rule_error(password)
        if rule_error:
            out(rule_error + " Nothing changed.")
            return 1
        if ask_secret("New password again: ") != password:
            out("The passwords do not match. Nothing changed.")
            return 1

        user.password = hash_password(password)
        user.must_change_password = True  # the system administrator knows this password
        code = recovery.set_new_code(user)
        recovery.record_event(db, user, recovery.CODE_CHANGED, ACTOR, "server")
        db.commit()
        out(f"Password changed for {user.username}.")
        out(f"New recovery code (shown only now, give it to the user): {code}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
