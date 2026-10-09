"""scripts/check_db_rights.py: reading SHOW GRANTS. Aiven runs MySQL with ANSI_QUOTES, so identifiers
come back in double quotes instead of backticks; both (and none) must give the same verdict.
No database needed: only the parser is tested."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "check_db_rights", Path(__file__).resolve().parents[1] / "scripts" / "check_db_rights.py")
check_db_rights = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_db_rights)  # main() only runs as a script
split_grants, EXPECTED = check_db_rights.split_grants, check_db_rights.EXPECTED_RIGHTS

BACKTICK = ["GRANT USAGE ON *.* TO `firemap_app`@`%`",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON `insurance_db`.* TO `firemap_app`@`%`"]
ANSI = ['GRANT USAGE ON *.* TO "firemap_app"@"%"',  # exactly what Aiven returned
        'GRANT SELECT, INSERT, UPDATE, DELETE ON "insurance_db".* TO "firemap_app"@"%"']
UNQUOTED = ["GRANT USAGE ON *.* TO firemap_app@%",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_db.* TO firemap_app@%"]


@pytest.mark.parametrize("grants", [BACKTICK, ANSI, UNQUOTED], ids=["backticks", "ansi_quotes", "unquoted"])
def test_the_least_privilege_account_passes_in_every_quote_style(grants):
    assert split_grants(grants, "insurance_db") == (EXPECTED, [])


@pytest.mark.parametrize("q", ["`", '"', ""], ids=["backticks", "ansi_quotes", "unquoted"])
def test_extra_rights_still_fail_in_every_quote_style(q):
    user = f"{q}firemap_app{q}@{q}%{q}"
    grants = [f"GRANT USAGE ON *.* TO {user}",
              f"GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP ON {q}insurance_db{q}.* TO {user}",
              f"GRANT SELECT ON {q}mysql{q}.* TO {user}",
              f"GRANT SELECT ON {q}insurance_db{q}.{q}users{q} TO {user}",  # table level: not db.*
              f"GRANT ALL PRIVILEGES ON *.* TO {user}"]
    rights, others = split_grants(grants, "insurance_db")
    assert rights == EXPECTED | {"CREATE", "DROP"}
    assert others == grants[2:]


def test_another_database_with_a_similar_name_is_not_ours():
    rights, others = split_grants(['GRANT SELECT ON "insurance_db_old".* TO "firemap_app"@"%"'], "insurance_db")
    assert rights == set() and len(others) == 1
