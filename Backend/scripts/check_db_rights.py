"""Checks a database account before the app is switched to it (IAS2 least privilege).

Run from Backend/ with the NEW account's URL in DATABASE_URL (and DB_SSL_CA for Aiven), e.g. in
PowerShell:
    $env:DATABASE_URL = "mysql+pymysql://firemap_app:<password>@<host>:<port>/insurance_db"
    $env:DB_SSL_CA = "C:/path/to/ca.pem"
    ./venv/Scripts/python scripts/check_db_rights.py
    Remove-Item Env:DATABASE_URL, Env:DB_SSL_CA

It never prints the URL or the password. Writes are made inside a transaction that is always
rolled back, so nothing is changed; the CREATE TABLE test uses a table name the app never uses
and drops it again if (wrongly) allowed. Exit code 0 = every check passed."""
import os
import re
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

EXPECTED_RIGHTS = {"SELECT", "INSERT", "UPDATE", "DELETE"}
TABLES = ["users", "policyholders", "ml_models", "login_events", "deleted_policyholders", "geocode_cache"]

failures = []
# "GRANT <rights> ON <object> TO ...". MySQL quotes identifiers with backticks, or with double quotes
# under ANSI_QUOTES (Aiven), or not at all.
GRANT_ON = re.compile(r"^GRANT (?P<rights>.+?) ON (?P<object>\S+) TO ")


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  - ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def split_grants(grants, db):
    """SHOW GRANTS lines -> (rights granted on the whole database `db`, every other grant except the
    global USAGE line, which only means "may log in")."""
    db_objects = {f"`{db}`.*", f'"{db}".*', f"{db}.*"}
    rights, others = set(), []
    for g in grants:
        m = GRANT_ON.match(g)
        if m and m["object"] in db_objects:
            rights |= {r.strip() for r in m["rights"].split(",")}
        elif not g.startswith("GRANT USAGE ON *.*"):
            others.append(g)
    return rights, others


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("Set DATABASE_URL first (it is not printed).")
    ca = os.environ.get("DB_SSL_CA")
    engine = create_engine(url, connect_args={"ssl": {"ca": ca}} if ca else {})

    with engine.connect() as conn:
        who, db = conn.execute(text("SELECT CURRENT_USER(), DATABASE()")).one()
        print(f"Connected as {who.split('@')[0]} to database {db}")
        check("not the admin account", not who.startswith(("avnadmin@", "root@")), who.split("@")[0])

        grants = [g[0] for g in conn.execute(text("SHOW GRANTS"))]
        for g in grants:
            print("      " + g)
        rights, others = split_grants(grants, db)
        check("rights on the database are exactly SELECT, INSERT, UPDATE, DELETE", rights == EXPECTED_RIGHTS,
              ", ".join(sorted(rights)))
        check("no rights anywhere else", not others, "; ".join(others))

        try:
            ssl = conn.execute(text("SHOW SESSION STATUS LIKE 'Ssl_cipher'")).one()[1]
            check("connection is encrypted (SSL)", bool(ssl) or not ca, ssl or "no SSL (fine only locally)")
        except DBAPIError as e:
            check("connection is encrypted (SSL)", False, str(e.orig))

        for t in TABLES:
            try:
                n = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
                check(f"SELECT {t}", True, f"{n} rows")
            except DBAPIError as e:
                check(f"SELECT {t}", False, str(e.orig))

        conn.rollback()  # end the read-only transaction SQLAlchemy opened by itself
        tx = conn.begin()
        try:
            conn.execute(text("INSERT INTO login_events (occurred_at, username, ip_address, result) "
                              "VALUES (UTC_TIMESTAMP(), 'ZZTEST rights check', '192.0.2.1', 'success')"))
            new_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            conn.execute(text("UPDATE login_events SET result = 'locked' WHERE id = :i"), {"i": new_id})
            conn.execute(text("DELETE FROM login_events WHERE id = :i"), {"i": new_id})
            check("INSERT, UPDATE, DELETE (rolled back)", True)
        except DBAPIError as e:
            check("INSERT, UPDATE, DELETE (rolled back)", False, str(e.orig))
        finally:
            tx.rollback()

        try:
            conn.execute(text("CREATE TABLE zz_rights_check_never_used (id INT PRIMARY KEY)"))
            conn.execute(text("DROP TABLE zz_rights_check_never_used"))
            check("CREATE TABLE is refused", False, "it was allowed (test table dropped again)")
        except DBAPIError as e:
            code = e.orig.args[0] if e.orig.args else None
            check("CREATE TABLE is refused", code == 1142, str(e.orig))

    print("\nAll checks passed." if not failures else f"\n{len(failures)} check(s) FAILED: {', '.join(failures)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
