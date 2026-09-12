#!/usr/bin/env python3
"""
Every platform link on a page belongs to THAT page's event, or is a dash.

    python3 verify/platform_links.py bordeaux_oct.html   # one line per problem

WHY THE OLD ASSERTION COULD NOT CATCH THE BUG IT WAS WRITTEN FOR
---------------------------------------------------------------
`assert_redesign.sh` asked two questions:

    1 Smartboard URL present
    Mio URLs == the number of "DICE · Mio" cards

Both were true of all seven pages while all seven linked to
`smartboard.shotgun.live/events/535882` and `mio.dice.fm/events/RXZlbnQ6NTczMjcx`
- epk's Shotgun id and epk's DICE relay, baked into the mock and copied onto
every page by pass 0. **A literal is present.** Counting presence cannot
distinguish this event's id from some other event's id, and the second question
was worse than useless: the card and the href came from the same literal, so
the count matched itself.

So this asks the only question that separates the two states: is the id in the
href the one `event_config.csv` gives THIS page.

WHAT A MISSING LINK LOOKS LIKE, AND WHY THAT IS NOT A FAILURE
--------------------------------------------------------------
Leo ruled the dash: where the config has no URL the row still renders, greyed,
with an em dash where the address goes. Three events have no `dice_mio_id` and
DICE genuinely does not sell them - a fact worth showing. So "no Mio URL" is
correct FOR THOSE THREE and wrong for the other four, and this check reads the
config to know which it is looking at rather than counting cards.

The Mio relay id is DERIVED (base64 of `Event:<id>`), so it is recomputed here
from `dice_mio_id` through `postprocess_html._dice_relay_id` - the same function
the builder calls. A tabulated expectation would be a second copy of an encoding
that already has one.

NEGATIVE TEST
-------------
Against the pre-fix tree (any commit before `54e83b8`, where the mock's epk
literals shipped on all seven):

    six of seven pages FAIL, epk.html passes - it is the event the literals
    belong to. Run 2026-09-12 against `origin/main`, verbatim:

      parisxxl      .../events/535882 is not this event's (want 494642)
                    .../RXZlbnQ6NTczMjcx is not this event's (want RXZlbnQ6NTI2NTM1)
      bordeaux      .../events/535882 is not this event's (want 505434)
                    .../RXZlbnQ6NTczMjcx is not this event's (want RXZlbnQ6NTQwMTk3)
      bordeaux_oct  .../events/535882 is not this event's (want 565846)
                    .../RXZlbnQ6NTczMjcx is linked but dice_mio_id is empty
      geneve        .../events/535882 is not this event's (want 546274)
                    .../RXZlbnQ6NTczMjcx is linked but dice_mio_id is empty
      rennes        .../events/535882 is not this event's (want 557151)
                    .../RXZlbnQ6NTczMjcx is not this event's (want RXZlbnQ6NjAwNDEz)
      sonora_impact .../events/535882 is not this event's (want 544355)
                    .../RXZlbnQ6NTczMjcx is linked but dice_mio_id is empty

Three of those name the empty-config arm rather than a wrong id, and that is
the arm the old assertion could not have: `bordeaux_oct`, `geneve` and
`sonora_impact` have no `dice_mio_id` at all, so epk's relay was not merely the
wrong link on those pages - it asserted a DICE backend that does not exist.

That epk alone stays green is the shape of the original defect, and is the
reason this is run per page rather than as one whole-set count.
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import postprocess_html  # noqa: E402
from static_region import static_region  # noqa: E402

SG_RE = re.compile(r'smartboard\.shotgun\.live/events/([^"\'<>\s]+)')
MIO_RE = re.compile(r'mio\.dice\.fm/events/([^/"\'<>\s]+)')


def config_row(page_name, config=None):
    """The ACTIVE config row whose `output_filename` is this page.

    `pages.py` enumerates page names from exactly this column, so a page the
    gate was handed always has one - and if it does not, that is a finding
    rather than a reason to skip the page silently.
    """
    path = Path(config or ROOT / 'event_config.csv')
    with path.open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if (row.get('status') or '').strip() != 'active':
                continue
            if (row.get('output_filename') or '').strip() == page_name:
                return row
    return None


def problems(page):
    """Every platform link on `page` that is not this event's, as strings."""
    page = Path(page)
    cfg = config_row(page.name)
    if cfg is None:
        return [f'{page.name}: no active event_config row names this page']

    html = page.read_text(encoding='utf-8')
    # The STATIC REGION, for the same reason every other count in the gate uses
    # it: the JS templates and the stylesheet are not markup a reader can click.
    body = static_region(html)

    out = []
    sg_id = (cfg.get('shotgun_event_id') or '').strip()
    mio_id = (cfg.get('dice_mio_id') or '').strip()
    want_mio = postprocess_html._dice_relay_id(mio_id) if mio_id else ''

    for label, found, want, field in (
            ('smartboard.shotgun.live/events', SG_RE.findall(body), sg_id,
             'shotgun_event_id'),
            ('mio.dice.fm/events', MIO_RE.findall(body), want_mio,
             'dice_mio_id')):
        # A SECOND LINK IS A FINDING, NOT A DUPLICATE TO DEDUPE. Two ids on one
        # page is precisely the half-substituted state - one row replaced, one
        # literal left - and `set()` here would hide it behind the right answer.
        if not want:
            if found:
                out.append(f'{page.name}: {label}/{found[0]} is linked but '
                           f'{field} is empty - it should render the dash')
            continue
        if not found:
            out.append(f'{page.name}: no {label} link, but {field} is {want!r}')
        for got in found:
            if got != want:
                out.append(f'{page.name}: {label}/{got} is not this event\'s '
                           f'(want {want})')
        if len(found) > 1:
            out.append(f'{page.name}: {len(found)} {label} links, want 1')
    return out


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[0])
        return 2
    bad = problems(sys.argv[1])
    for b in bad:
        print(b)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
