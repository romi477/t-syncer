#!/usr/bin/env python3
"""One-shot migration: worklogs.tag_id (number) -> worklogs.tag (code string).

Run it once against the database of a T-Syncer that was built before the tag
became a string. Stop the app first: the old code reads tag_id and the new code
reads tag, so nothing should be writing while the column changes.

    ./scripts/docker-stop.sh
    python3 scripts/migrate_tag_to_code.py tsyncer.db
    ./scripts/docker-run.sh

Standard library only, no imports from the app: it runs with any python3, on the
host or inside the container. Safe to run twice - it reports and exits.
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Frozen history: the numbers the old catalogue used. Not the current catalogue.
LEGACY_TAG_IDS = {
    1: "DEV",
    2: "SUP",
    3: "QA",
    4: "DOC",
    5: "REL",
    6: "INT",
    7: "DEM",
}


def columns(con: sqlite3.Connection, table: str) -> set[str]:

    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def back_up(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    copy = path.with_name(f"{path.name}.backup-{stamp}")
    shutil.copy2(path, copy)

    return copy


def migrate(path: Path) -> int:
    con = sqlite3.connect(path)
    con.isolation_level = None
    try:
        present = columns(con, "worklogs")
        if "worklogs" not in {row[0] for row in con.execute(
            "select name from sqlite_master where type='table'"
        )}:
            print(f"{path}: no worklogs table - is this a T-Syncer database?")

            return 1
        if "tag_id" not in present:
            print(f"{path}: already migrated, nothing to do")

            return 0

        copy = back_up(path)
        print(f"backup: {copy}")

        con.execute("BEGIN")
        if "tag" not in present:
            con.execute("ALTER TABLE worklogs ADD COLUMN tag TEXT NOT NULL DEFAULT ''")
        for tag_id, code in LEGACY_TAG_IDS.items():
            con.execute(
                "UPDATE worklogs SET tag = ? WHERE tag_id = ? AND tag = ''", (code, tag_id)
            )
        unknown = con.execute(
            "SELECT count(*) FROM worklogs WHERE tag = '' AND tag_id IS NOT NULL"
        ).fetchone()[0]
        try:
            con.execute("ALTER TABLE worklogs DROP COLUMN tag_id")
            dropped = True
        except sqlite3.OperationalError:
            # DROP COLUMN needs SQLite 3.35+. Older ones keep the dead column,
            # which costs nothing: no code reads it any more.
            dropped = False
        con.execute("COMMIT")

        for code, count in con.execute(
            "SELECT tag, count(*) FROM worklogs GROUP BY tag ORDER BY count(*) DESC"
        ):
            print(f"  {code or '(no tag)':<9} {count}")
        if unknown:
            print(f"  {unknown} line(s) had a tag id outside the catalogue; left without a tag")
        if not dropped:
            print("  note: this SQLite cannot DROP COLUMN; tag_id was left in place, unused")
        print(f"{path}: migrated")

        return 0
    finally:
        con.close()


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        print("usage: migrate_tag_to_code.py <path to tsyncer.db>")

        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"{path}: not a file")

        return 1

    return migrate(path)


if __name__ == "__main__":
    raise SystemExit(main())
