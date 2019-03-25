#
# Library code for ACCU website
#

import pathlib

# Standard path (URL part after site) generators
def article_path(journal, year, month, title):
    p = pathlib.Path("journal") / journal.casefold() / year / month.casefold()
    fname = ""
    for c in title.casefold():
        if c.isspace():
            fname += "_"
            continue
        if c.isalnum():
            fname += c
        continue
    p = p / fname
    return str(p) + ".adoc"

def link_path(linkno):
    p = pathlib.Path("journal") / "index" / linkno
    return str(p)
