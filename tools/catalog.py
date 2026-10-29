# SPDX-License-Identifier: GPL-3.0-or-later
"""The message catalog's files (pt-BR design 7.1), run from the repo root with the dev venv's Python after a change to
CATALOG or to a .po: `python tools/catalog.py [LANG...]`. It writes po/kicad_rf_studio.pot from core.messages.CATALOG,
each entry's code its extracted comment (`pybabel extract` cannot read a dict's values); updates each po/<lang>.po from
it, making one for each LANG named that has none (a new or changed template comes back with an empty msgstr, the old
pair kept at the file's end as an obsolete #~ entry; a line it cannot parse stops it with a PoFileError naming the
line); and compiles each .po's translated entries into src/kicad_rf_studio/locale/<lang>/LC_MESSAGES/kicad_rf_studio.mo,
which is committed: the wheel compiles nothing. No header it writes holds an address or a date: Babel's defaults hold
placeholder addresses, one of which the privacy gate's e-mail rule matches, and a date would change every file on every
run. Babel, pinned in the dev extra (each header names its version), does the work; the package and the tests never
import it."""
import datetime
import io
import re
import sys
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

from kicad_rf_studio import __version__
from kicad_rf_studio.core.messages import CATALOG, LOCALE

PO = Path(__file__).resolve().parents[1] / "po"
DOMAIN = "kicad_rf_studio"
UNSHARED = re.compile(  # the header lines that hold an address or a date
    rb'^"(Report-Msgid-Bugs-To|POT-Creation-Date|PO-Revision-Date|Last-Translator|Language-Team):.*\n', re.M)
# ponytail: Babel always writes a .mo's POT-Creation-Date, so it holds the epoch: no real date, and the same bytes from
# the same .po
EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def write(path: Path, catalog: Catalog) -> None:
    """`catalog` as a .po (or .pot) at `path`: each string on one line but split after each \\n, no python-format flag
    (Babel's guess at "4.6 % off"), and none of the UNSHARED header lines."""
    for message in catalog:  # Babel sets the flag again on every read, so it goes here
        message.flags.discard("python-format")
    out = io.BytesIO()
    write_po(out, catalog, width=0)
    path.write_bytes(UNSHARED.sub(b"", out.getvalue()))


def main(argv: list[str]) -> int:
    template = Catalog(domain=DOMAIN, project="kicad-rf-studio", version=__version__, fuzzy=False,
                       header_comment="# kicad-rf-studio's messages: tools/catalog.py writes this template.")
    for code, text in CATALOG.items():
        template.add(text, auto_comments=[code])
    PO.mkdir(exist_ok=True)
    write(PO / f"{DOMAIN}.pot", template)
    for lang in sorted({p.stem for p in PO.glob("*.po")} | set(argv)):
        path = PO / f"{lang}.po"
        if path.exists():
            with path.open("rb") as f:
                catalog = read_po(f, abort_invalid=True)  # a damaged line stops it, never a msgstr cut short
        else:
            catalog = Catalog(locale=lang, domain=DOMAIN, project="kicad-rf-studio", version=__version__, fuzzy=False,
                              header_comment=f"# kicad-rf-studio's messages in {lang}: translate each msgstr here, "
                                             "then run tools/catalog.py.")
        catalog.update(template, no_fuzzy_matching=True)  # never a neighbour's msgstr guessed into a new msgid
        write(path, catalog)
        catalog.msgid_bugs_address = catalog.last_translator = catalog.language_team = ""
        catalog.creation_date = catalog.revision_date = EPOCH
        mo = LOCALE / lang / "LC_MESSAGES" / f"{DOMAIN}.mo"
        mo.parent.mkdir(parents=True, exist_ok=True)
        with mo.open("wb") as f:
            write_mo(f, catalog)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
