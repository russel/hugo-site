#
# Library code for ACCU website
#

import pathlib
import re

# Convert article XML or HTML to HTML or AsciiDoc.
import bs4

class ConversionError(Exception):
    def __init__(self, msg):
        super().__init__("Conversion error {}".format(msg))

class BaseOutput:
    def convert_document(self, soup):
        """ Convert the document and return the converted text."""
        return ''.join(self.convert(soup))

    @staticmethod
    def has_class(tag, classname):
        """ See if tag has a class of given name.

        BS behaves returns a list of classes on HTML input, and
        a single class in XML input. Deal with both.
        """
        cl = tag.get('class')
        if not cl:
            return False
        if isinstance(cl, list):
            return classname in cl
        else:
            return classname == cl

    def convert(self, soup):
        """ Convert everything below this tag.

        Return a list of strings.
        """
        if isinstance(soup, (bs4.Comment, bs4.CData, bs4.ProcessingInstruction,
                             bs4.Declaration, bs4.Doctype)):
            return []
        if isinstance(soup, bs4.NavigableString):
            return self.get_string(soup.string)
        elif isinstance(soup, bs4.Tag):
            tag_name = soup.name
            if tag_name == '[document]':
                tag_name = 'document_root'
            return getattr(self, tag_name, self.unknown_tag)(soup)
        else:
            return []

    def convert_children(self, soup):
        res = []
        for c in soup.children:
            res.extend(self.convert(c))
        return res

    def get_string(self, s):
        return [s]

    def document_root(self, tag):
        return self.convert_children(tag)

    def xml(self, tag):
        return self.convert_children(tag)

    def html(self, tag):
        return self.convert_children(tag)

    def body(self, tag):
        return self.convert_children(tag)

    def unknown_tag(self, tag):
        raise ConversionError('Unknown Tag {}'.format(tag.name))

class AdocOutput(BaseOutput):
    def __init__(self, title=None, author=None, summary=None, includebio=False):
        self.title = title
        self.author = author
        self.summary = summary
        self.bio = None
        self.includebio = includebio
        self.ul_level = 1
        self.ol_level = 1
        self.table_level = -1
        self.table_cell_delim = ['¦', '!']
        self.table_delim_start = ['[separator=¦]\n|===', '!===']
        self.table_delim_end = ['|===', '!===']
        self.list_item = []
        self.in_pre = False
        self.in_biblio_ref = False
        self.in_biblio_re = re.compile(r'\[.+?\]\s*(?P<ref>.*)')
        self.table_listing_re = re.compile('(?P<prelude>.*)\n\\[separator=¦\\]\n\\|===\n\s*a¦\s+(?P<src>\\[source\\]\n----\n.*?\n----)\s*\n\s*h¦(?P<id>.*?)\n\\|===\n(?P<postlude>.*)', re.DOTALL)
        self.table_image_re = re.compile('(?P<prelude>.*)\n\\[separator=¦\\]\n\\|===\n\s*a¦\s+image::(?P<img>.*?)\\[\\]\n\s*h¦(?P<id>.*?)\n\\|===\n(?P<postlude>.*)', re.DOTALL)

    @staticmethod
    def trim(text, spaces=True):
        while text and not text[0].strip():
            del text[0]
        while text and not text[-1].strip():
            del text[-1]
        if text:
            text[0] = text[0].lstrip('\n')
            text[-1] = text[-1].rstrip()
        if spaces and text:
            text[0] = text[0].lstrip()
        return text

    def get_string(self, s):
        if self.in_biblio_ref:
            # Remove initial [?] plus spaces.
            match = self.in_biblio_re.search(s)
            if match:
                s = match.group('ref')
        if not self.in_pre:
            # This appears to be a regular image bug.
            if s == ' />':
                s = ''
            s = s.replace('\n', ' ')\
                .replace('[', 'pass:[[]')
        s = s.replace('C++', '{cpp}')
        # TODO. Prevent character substitution on =>, <=, -> <=>.
        return [s]

    def p(self, tag):
        if self.has_class(tag, 'bio'):
            self.bio = ['\n\n.{author}\n****\n'] + self.trim(self.convert_children(tag)) + ['\n****']
            return []
        elif self.has_class(tag, 'quote'):
            # This is a bit nasty. We want the formatted text (so we include
            # e.g. <br> in the quote), but only up to text starting '~ '.
            # The rest, unformatted, should be <author>,<source>.
            # But the separator may itself be in formatted text. I've seen
            # author and source formatted <em> and <strong>. So we have to
            # ignore items from the separator onwards.
            quote = []
            for c in tag.children:
                if c.string and c.string.lstrip().startswith('~ '):
                    break
                else:
                    quote.extend(self.convert(c))
            quote = self.trim(quote)
            by = tag.get_text().rsplit('~ ', 1)[1].replace('\n', '')
            return ['\n\n[quote,{by}]\n____\n'.format(by=by)] + quote + ['\n____']
        elif self.has_class(tag, 'blockquote'):
            return self.blockquote(tag)
        elif self.has_class(tag, 'Byline'):
            self.summary = self.trim(self.convert_children(tag))
            return []
        elif self.has_class(tag, 'bibliomixed'):
            # These are a single reference. The first child is the anchor.
            # This is followed by text starting with the reference '[n]',
            # then spaces and then the body of the reference, e.g.:
            #
            # <a id="[2]"></a>[2]      Principles behind the Agile Manifesto
            #
            # For AsciiDoctor we need to remove the reference text and
            # spaces, and present each reference as an item in an unordered
            # list.
            self.in_biblio_ref = True
            ref = self.convert_children(tag)
            self.in_biblio_ref = False
            return ['\n\n- '] + ref
        else:
            return ['\n\n'] + self.trim(self.convert_children(tag))

    def blockquote(self, tag):
        return ['\n\n====\n'] + self.trim(self.convert_children(tag)) + ['\n====']

    def code(self, tag):
        return ['`'] + self.convert_children(tag) + ['`']

    def tt(self, tag):
        return self.code(tag)

    def em(self, tag):
        return ['_'] + self.convert_children(tag) + ['_']

    def i(self, tag):
        return self.em(tag)

    def strong(self, tag):
        return ['*'] + self.convert_children(tag) + ['*']

    def sup(self, tag):
        return ['^'] + self.convert_children(tag) + ['^']

    def sub(self, tag):
        return ['~'] + self.convert_children(tag) + ['~']

    def span(self, tag):
        if self.has_class(tag, 'author'):
            self.author = ''.join(self.convert_children(tag))
            return []
        else:
            return ['*'] + self.convert_children(tag) + ['*']

    def h1(self, tag):
        self.title = ''.join(self.convert_children(tag))
        return []

    def hn(self, tag, n):
        # Any header block 'References' may have a bibliography.
        title = self.convert_children(tag)
        hdr = '=' * n
        if ''.join(title) == 'References':
            hdr = '[bibliography]\n' + hdr
        return [ '\n\n' + hdr + ' '] + title

    def h2(self, tag):
        return self.hn(tag, 2)

    def h3(self, tag):
        return self.hn(tag, 3)

    def h4(self, tag):
        return self.hn(tag, 4)

    def h5(self, tag):
        return self.hn(tag, 5)

    def h6(self, tag):
        return self.hn(tag, 6)

    def pre(self, tag):
        self.in_pre = True
        src = self.convert_children(tag)
        self.in_pre = False
        return ['\n\n[source]\n----\n'] + self.trim(src, False) + ['\n----']

    def br(self, tag):
        return [' +\n']

    def ul(self, tag):
        self.list_item.append('*' * self.ul_level)
        self.ul_level += 1
        res = self.convert_children(tag)
        self.ul_level -= 1
        self.list_item.pop()
        return res

    def ol(self, tag):
        self.list_item.append('.' * self.ol_level)
        self.ol_level += 1
        res = self.convert_children(tag)
        self.ol_level -= 1
        self.list_item.pop()
        return res

    def li(self, tag):
        # If there are blank lines in the item, replace with '+' to
        # keep everything with the current bullet.
        item = self.trim(self.convert_children(tag))
        lines = ''.join(item).splitlines()
        for i in range(len(lines)):
            if not lines[i].strip():
                lines[i] = '+'
        return ['\n\n{} '.format(self.list_item[-1])] + ['\n'.join(lines)]

    def table(self, tag):
        self.table_level += 1
        if self.table_level >= len(self.table_cell_delim):
            raise ConversionError('Sorry, I can\'t nest tables deeper than {}'.format(self.table_level))
        sidebar = self.has_class(tag, 'sidebartable')
        if sidebar:
            res = ['\n\n****\n{}\n'.format(self.table_delim_start[self.table_level])]
        else:
            res = ['\n\n{}\n'.format(self.table_delim_start[self.table_level])]
        res = res + self.trim(self.convert_children(tag))
        if sidebar:
            res = res + ['\n{}\n****'.format(self.table_delim_end[self.table_level])]
        else:
            res = res + ['\n{}'.format(self.table_delim_end[self.table_level])]
        self.table_level -= 1

        # Look out for particular table formations and replace with
        # more appropriate markup.
        s = ''.join(res)
        match = self.table_listing_re.fullmatch(s)
        if match:
            return [ '{prelude}\n.{id}\n{src}\n{postlude}'.format(
                prelude=match.group('prelude'),
                src=match.group('src'),
                id=match.group('id'),
                postlude=match.group('postlude')) ]
        match = self.table_image_re.fullmatch(s)
        if match:
            return [ '{prelude}\n.{id}\nimage::{img}[{id}]\n{postlude}'.format(
                prelude=match.group('prelude'),
                img=match.group('img'),
                id=match.group('id'),
                postlude=match.group('postlude')) ]
        return res

    def tr(self, tag):
        return ['\n\n'] + self.convert_children(tag)

    def td(self, tag):
        if self.has_class(tag, 'title'):
            res = [' h{}'.format(self.table_cell_delim[self.table_level])]
        else:
            res = [' a{}'.format(self.table_cell_delim[self.table_level])]
        return res + self.convert_children(tag)

    def th(self, tag):
        return [' h{}'.format(self.table_cell_delim[self.table_level])] + self.convert_children(tag)

    def a(self, tag):
        id = tag.get('id')
        if not id:
            id = tag.get('name')
        if id:
            if id[0] == '[' and id[-1] == ']':
                # It's a bibliography entry. These should have no content.
                id = id[1:-1]
                return ['[[[ref{id},{id}]]] '.format(id=id)]
            else:
                # Define an anchor.
                return ['[[ref{id},{id}]] '.format(id=id)] + self.convert_children(tag)
        href = tag.get('href')
        if href:
            if href.startswith('#[') and href.endswith(']'):
                # It's a biblio reference. Add reference. The content should
                # just repeat the reference.
                return ['<<ref{ref}>>'.format(ref=href[2:-1])]
            else:
                # It's a regular link.
                return ['link:{url}['.format(url=href)] + self.convert_children(tag) + [']']
        return []

    def img(self, tag):
        src = tag.get('src')
        if src.startswith('http://accu.org'):
            src = src.replace('http://accu.org/content/images/', '', 1)
        if src.startswith('/content/images/'):
            src = src.replace('/content/images/', '', 1)
        return ['\nimage::{src}[]\n'.format(src=src)]

    def convert_document(self, soup):
        """ Convert the document and return the converted text."""
        body = self.convert(soup)
        res = [ '= {title}\n'.format(title=self.title) ]
        if self.summary:
            res = res + [ '\n\n[.lead]\n'] + self.summary
        if self.author:
            res = res + [ ':author: {author}\n'.format(author=self.author) ]
        res = res + [ ':imagesdir: https://accu.org/content/images/\n:figure-caption!:\n' ] + body
        if self.bio and self.includebio:
            res = res + self.bio
        return ''.join(res)

class HtmlOutput(BaseOutput):
    pass
    def __init__(self):
        self.bio = None

    def unknown_tag(self, tag):
        return [tag.prettify()]

    def p(self, tag):
        if self.has_class(tag, 'bio'):
            self.bio = tag.prettify()
            return []
        else:
            return [tag.prettify()]

    def convert_document(self, soup):
        """ Convert the document and return the converted text."""
        body = self.convert(soup)
        res = ['<html>\n'] + body
        if self.bio:
            res = res + [self.bio]
        res = res + ['</html>']
        return ''.join(res)

# Helper functions for standard conversions.
def convert_article(source, inputformat, outputformat, title, author, summary, includebio=False):
    """convert XML or HTML article input to adoc or HTML.

       source: input data - file or string.
       inputformat: 'xml' or 'html'.
       outputformat: 'adoc' or 'html'.
       title: article title
       author: article author

       returns converted text.

       throws ConversionError."""
    parsers = {
        "xml": "lxml-xml",
        "html": "lxml"
        }
    outputs = {
        "adoc": AdocOutput(title=title, author=author, summary=summary, includebio=includebio),
        "html": HtmlOutput()
    }

    try:
        infmt = parsers[inputformat]
    except KeyError:
        raise ConversionError('inputformat must be "xml" or "html"')
    try:
        outfmt = outputs[outputformat]
    except KeyError:
        raise ConversionError('outputformat must be "adoc" or "html"')

    soup = bs4.BeautifulSoup(source, infmt)
    return outfmt.convert_document(soup)

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
