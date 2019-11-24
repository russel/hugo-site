#
# Library code for ACCU website article extraction.
#

import json
import pathlib
import re
import urllib.parse

# Standard path (URL part after site) generators
def article_dir(journal, year, month):
    return pathlib.Path("journal") / journal.casefold() / year / month[0:3].casefold()

def article_title_to_filename(title):
    fname = ""
    for c in title.casefold():
        if c.isspace():
            fname += "_"
            continue
        if c.isalnum() and c.isascii():
            fname += c
        continue
    return fname

def article_path(journal, year, month, title):
    p = article_dir(journal, year, month)
    p = p / article_title_to_filename(title)
    return str(p) + ".adoc"

def link_path(linkno):
    p = pathlib.Path("journal") / "index" / linkno
    return str(p)

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

        BS returns a list of classes on HTML input, and
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

    def image_renames(self):
        return []

class AdocOutput(BaseOutput):
    def __init__(self, title=None, author=None, summary=None, includebio=False):
        self.title = title
        self.title_filename = None
        if title:
            self.title_filename = article_title_to_filename(title)
        self.author = author
        if summary:
            self.summary = [ summary ]
        else:
            self.summary = None
        self.bio = None
        self.includebio = includebio
        self.ul_level = 1
        self.ol_level = 1
        self.table_level = -1
        self.table_cell_delim = ['¦', '!']
        self.table_delim_start = ['[separator=¦]\n|===', '!===']
        self.table_delim_end = ['|===', '!===']
        self.list_item = []
        self.image_rename = []
        self.image_index = 0
        self.swallow_next_leading_space = False
        self.in_pre = False
        self.in_biblio_ref = False
        self.in_biblio_re = re.compile(r'\[.+?\]\s*(?P<ref>.*)')
        self.table_listing_re = re.compile('(?P<prelude>.*)\n\\[separator=¦\\]\n\\|===\n\s*a¦\s+(?P<src>\\[source\\]\n----\n.*?\n----)\s*\n\s*h¦(?P<id>.*?)\n\\|===\n(?P<postlude>.*)', re.DOTALL)
        self.table_image_re = re.compile('(?P<prelude>.*)\n\\[separator=¦\\]\n\\|===\n\s*a¦\s+image::(?P<img>.*?)\\[\\]\n\s*h¦(?P<id>.*?)\n\\|===\n(?P<postlude>.*)', re.DOTALL)
        self.tidy_xref_re = re.compile(r'pass:\[\[\](?P<ref><<.*?>>)\]')

    # Tidy reference IDs. Make sure they don't contain characters other than
    # alphanumeric and _.
    @staticmethod
    def tidy_ref_id(ref):
        return ''.join([c if c.isalnum() or c == '_' else '_' for c in ref])

    def join_list(self, l):
        res = ''
        for item in l:
            if callable(item):
                res += item(res)
            elif isinstance(item, str):
                if self.swallow_next_leading_space:
                    item = item.lstrip()
                    print(item)
                    if item:
                        self.swallow_next_leading_space = False
                res += item
            else:
                raise ConversionError('Unexpected item {}'.format(item))
        return res

    def to_line_start(self, s):
        return '' if len(s) == 0 or s.endswith('\n') else '\n'

    def swallow_leading_space(self, s):
        self.swallow_next_leading_space = True
        return ''

    def blank_line_before(self):
        return [self.to_line_start, '+\n' if len(self.list_item) > 0 else '\n']

    def imgpath(self, src):
        if not src:
            raise ConversionError('Image with no src tag')
        if src.startswith('http://accu.org/'):
            src = src.replace('http://accu.org/', '/', 1)
        if src.startswith('/content/images/'):
            p = pathlib.Path(src)
            newsrc = '{title}_{idx}{suffix}'.format(
                title=self.title_filename,
                idx = self.image_index,
                suffix = p.suffix)
            self.image_index += 1
            self.image_rename.append((src, newsrc))
            return newsrc
        else:
            return src

    def get_string(self, s):
        s = s.replace('\r', '')
        if self.in_biblio_ref:
            # Remove initial [?] plus spaces.
            match = self.in_biblio_re.search(s)
            if match:
                s = match.group('ref')
        if not self.in_pre:
            # This appears to be a regular image bug.
            if s == ' />':
                s = ''
            s = s.replace('C++', '{cpp}')
            s = s.replace('\n', ' ')\
                .replace('[', 'pass:[[]')\
                .replace('+', 'pass:[+]')\
                .replace('`', 'pass:[`]')\
                .replace('_', 'pass:[_]')\
                .replace('^', 'pass:[^]')\
                .replace('~', 'pass:[~]')\
                .replace('*', 'pass:[*]')
        # TODO. Prevent character substitution on =>, <=, -> <=>.
        return [s]

    def strip_para_start(self, s):
        while s and (callable(s[0]) or s[0] == '+\n' or not s[0].strip()):
            del s[0]
        return s

    def p(self, tag):
        if self.has_class(tag, 'bio'):
            self.bio = self.blank_line_before() + ['.{author}\n****\n'] + self.convert_children(tag) + [self.to_line_start, '****\n', self.swallow_leading_space]
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
            quote = quote
            split = tag.get_text().rsplit('~ ', 1)
            if len(split) > 1:
                by = split[1].replace('\n', '')
            else:
                # No '~ '. Check for simpler format, quote '-' author.
                split = quote[-1].rsplit(' - ', 1)
                if len(split) > 1:
                    by = split[1].replace('\n', '')
                    quote[-1] = split[0]
                else:
                    by = None
            if by:
                return self.blank_line_before() + ['[quote,{by}]\n____\n'.format(by=by)] + quote + [self.to_line_start, '____\n', self.swallow_leading_space]
            else:
                return self.blank_line_before() + ['[quote]\n____\n'] + quote + [self.to_line_start, '____\n', self.swallow_leading_space]
        elif self.has_class(tag, 'blockquote'):
            return self.blockquote(tag)
        elif self.has_class(tag, 'Byline'):
            self.summary = self.convert_children(tag)
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
            return [self.to_line_start, '- '] + ref + [self.to_line_start]
        else:
            para = self.convert_children(tag)
            if para and not callable(para[0]):
                para[0] = para[0].lstrip()
            return self.blank_line_before() + para

    def blockquote(self, tag):
        return self.blank_line_before() + ['====\n'] + self.convert_children(tag) + [self.to_line_start, '====\n', self.swallow_leading_space]

    def code(self, tag):
        if self.in_pre:
            return self.convert_children(tag)
        else:
            return ['``'] + self.convert_children(tag) + ['``']

    def tt(self, tag):
        return self.code(tag)

    def b(self, tag):
        return self.strong(tag)

    def em(self, tag):
        return ['__'] + self.convert_children(tag) + ['__']

    def u(self, tag):
        return self.em(tag)

    def i(self, tag):
        return self.em(tag)

    def cite(self, tag):
        return self.em(tag)

    def strong(self, tag):
        return ['**'] + self.convert_children(tag) + ['**']

    def sup(self, tag):
        return ['^'] + self.convert_children(tag) + ['^']

    def sub(self, tag):
        return ['~'] + self.convert_children(tag) + ['~']

    def big(self, tag):
        return self.convert_children(tag)

    def footer(self, tag):
        return ['('] + self.convert_children(tag) + [')']

    def span(self, tag):
        # Span usage in journals always has <b></b> interior.
        return self.convert_children(tag)

    def hr(self, tag):
        return self.blank_line_before() + ["'''\n", self.swallow_leading_space]

    def div(self, tag):
        return self.convert_children(tag)

    def h1(self, tag):
        self.title = self.join_list(self.convert_children(tag))
        self.title_fname = article_title_to_filename(self.title)
        return []

    def hn(self, tag, n):
        # Any header block 'References' may have a bibliography.
        title = self.convert_children(tag)
        hdr = '=' * n
        if self.join_list(title) == 'References':
            hdr = '[bibliography]\n' + hdr
        return self.blank_line_before() + [hdr + ' '] + title + ['\n', self.swallow_leading_space]

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
        return self.blank_line_before() + ['[source]\n----\n'] + src + ['\n----\n', self.swallow_leading_space]

    def br(self, tag):
        return [' +\n', self.swallow_leading_space] + self.convert_children(tag)

    def ul(self, tag):
        self.list_item.append('*' * self.ul_level)
        self.ul_level += 1
        res = self.convert_children(tag)
        self.ul_level -= 1
        self.list_item.pop()
        return self.blank_line_before() + res

    def ol(self, tag):
        self.list_item.append('.' * self.ol_level)
        self.ol_level += 1
        res = self.convert_children(tag)
        self.ol_level -= 1
        self.list_item.pop()
        return self.blank_line_before() + res

    def li(self, tag):
        if len(self.list_item) < 1:
            raise ConversionError('List item without enclosing list')
        # Look out for a list item that starts with a continuation.
        # AsciiDoctor doesn't expect continuations before you have anything.
        item = self.strip_para_start(self.convert_children(tag))
        return [self.to_line_start, self.list_item[-1] + ' '] + item + [self.to_line_start, self.swallow_leading_space]

    def dl(self, tag):
        return self.blank_line_before() + self.convert_children(tag) + [self.to_line_start, self.swallow_leading_space]

    def dt(self, tag):
        return self.blank_line_before() + self.convert_children(tag) + ['::']

    def dd(self, tag):
        dd = self.strip_para_start(self.convert_children(tag))
        return [self.to_line_start] + dd

    def table(self, tag):
        self.table_level += 1
        if self.table_level >= len(self.table_cell_delim):
            raise ConversionError('Sorry, I can\'t nest tables deeper than {}'.format(self.table_level))
        sidebar = self.has_class(tag, 'sidebartable')
        if sidebar:
            res = self.blank_line_before() + ['****\n{}\n'.format(self.table_delim_start[self.table_level])]
        else:
            res = self.blank_line_before() + ['{}\n'.format(self.table_delim_start[self.table_level])]
        res = res + self.convert_children(tag)
        if sidebar:
            res = res + self.blank_line_before() + ['{}\n****\n'.format(self.table_delim_end[self.table_level]), self.swallow_leading_space]
        else:
            res = res + self.blank_line_before() + ['{}\n'.format(self.table_delim_end[self.table_level]), self.swallow_leading_space]
        self.table_level -= 1

        return res
        # Look out for particular table formations and replace with
        # more appropriate markup.
        s = self.join_list(res)
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
                img=self.imgpath(match.group('img')),
                id=match.group('id'),
                postlude=match.group('postlude')) ]
        return res

    def tr(self, tag):
        return self.blank_line_before() + self.convert_children(tag)

    def td(self, tag):
        if tag.has_attr('colspan'):
            colspan = tag['colspan'] + '+'
        else:
            colspan = ''
        if self.has_class(tag, 'title'):
            res = [' {}h{}'.format(colspan, self.table_cell_delim[self.table_level])]
        else:
            res = [' {}a{}'.format(colspan, self.table_cell_delim[self.table_level])]
        return res + self.convert_children(tag)

    def th(self, tag):
        return [' h{}'.format(self.table_cell_delim[self.table_level])] + self.convert_children(tag)

    def colgroup(self, tag):
        return []

    def thead(self, tag):
        return self.convert_children(tag)

    def tbody(self, tag):
        return self.convert_children(tag) + [self.to_line_start]

    def a(self, tag):
        id = tag.get('id')
        if not id:
            id = tag.get('name')
        if id:
            if id[0] == '[' and id[-1] == ']':
                # It's a bibliography entry. These should have no content.
                id = id[1:-1]
                return ['[[[ref{rid},{id}]]] '.format(rid=self.tidy_ref_id(id), id=id)]
            else:
                # Define an anchor.
                return ['[[ref{rid},{id}]]'.format(rid=self.tidy_ref_id(id), id=id)] + self.convert_children(tag)
        href = tag.get('href')
        if href:
            if href.startswith('#[') and href.endswith(']'):
                # It's a biblio reference. Add reference. The content should
                # just repeat the reference.
                return ['<<ref{ref}>>'.format(ref=self.tidy_ref_id(href[2:-1]))]
            else:
                # It's a regular link.
                return ['link:{url}['.format(url=href)] + self.convert_children(tag) + [']']
        return []

    def img(self, tag):
        src = self.imgpath(tag.get('src'))
        return [self.to_line_start, 'image::{src}[]\n'.format(src=src), self.swallow_leading_space]

    def tidy_adoc(self, adoc):
        # Strip any [] around an inline ref.
        res = self.tidy_xref_re.sub(lambda m: m.group('ref'), adoc)
        return res

    def convert_document(self, soup):
        """ Convert the document and return the converted text."""
        body = self.convert(soup)
        res = [ '= {title}\n'.format(title=self.title) ]
        if self.author:
            res = res + [ ':author: {author}\n'.format(author=self.author) ]
        res = res + [ ':figure-caption!:\n:imagesdir: ..\n' ]
        if self.summary:
            res = res + [ '\n[.lead]\n' ] + self.summary + ['\n\n']
        res = res + body
        if self.bio and self.includebio:
            res = res + self.bio
        return self.tidy_adoc(self.join_list(res))

    def image_renames(self, basedir=''):
        res = []
        for ren in self.image_rename:
            p = pathlib.Path(basedir) / ren[1]
            res.append('cp ".{}" {}'.format(urllib.parse.unquote(ren[0]).strip(), str(p)))
        return res

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
        """ Convert the document and return the conversion."""
        body = self.convert(soup)
        res = ['<html>\n'] + body
        if self.bio:
            res = res + [self.bio]
        res = res + ['</html>']
        return ''.join(res)

# Helper functions for standard conversions.
def convert_article(source, inputformat, outputformat, title, author, summary, imagedir='', includebio=False):
    """convert XML or HTML article input to adoc or HTML.

       source: input data - file or string.
       inputformat: 'xml' or 'html'.
       outputformat: 'adoc' or 'html'.
       title: article title
       author: article author

       returns tuple of converted text and list of image renames.

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
    return (outfmt.convert_document(soup), outfmt.image_renames(imagedir))

# Bibliography stuff
class BibSyntaxError(Exception):
    """Exception raised for errors in a bib file.

    Attributes:
        lineno -- line number of line with error
        line -- line content with error
        message -- explanation of the error
    """

    def __init__(self, lineno, line, message):
        self.lineno = lineno
        self.line = line
        self.message = message

def readbib(f, volume=None, number=None):
    articles = []
    in_article = False
    line_no = 0
    for l in f.readlines():
        line_no = line_no + 1
        l = l.strip()
        if not l:
           continue
        if l[0] == '%':
           continue
        if l == '}':
           if in_article:
               in_article = False
               if volume and article['Volume'] != volume:
                   continue
               if number and article['Number'] != number:
                   continue
               articles.append(article)
               continue
           else:
               raise BibSyntaxError(line_no, l, "'}' outside article definition")
        if l == '@Article{':
            if not in_article:
                in_article = True
                article = {}
                article['Author'] = []
                continue
            else:
                raise BibSyntaxError(line_no, l, "'@Article{' inside article definition")

        if not in_article:
            raise BibSyntaxError(line_no, l, "Not in article definition")

        key, val = l.split('=', 1)
        val = val.strip()
        if key == 'Author':
            article[key].append(val)
        elif key in article:
            raise BibSyntaxError(line_no, l, "Value already specified")
        else:
            article[key] = val
    if in_article:
        raise BibSyntaxError(line_no + 1, "", "End of file inside article")
    return articles

# JSON file stuff
def read_json(f, bib_author_name_format=False):
    journal_re = re.compile(r'(?P<name>\w+)\s*Journal.*\- (?P<month>.*)\s*(?P<year>\d{4})')
    issue_re = re.compile(r'o?\d+')
    month_abbrev = {
        'Jan': 'January',
        'Feb': 'February',
        'Mar': 'March',
        'Apr': 'April',
        'May': 'May',
        'Jun': 'June',
        'Jul': 'July',
        'Aug': 'August',
        'Sep': 'September',
        'Oct': 'October',
        'Nov': 'November',
        'Dec': 'December'
        }
    id_fixups = {
        # Overload test issue 1
        1805: ('Overload', '2013', 'July'),
        1806: ('Overload', '2013', 'July'),
        1807: ('Overload', '2013', 'July'),
        1808: ('Overload', '2013', 'July'),

        # Overload test issue 2
        1821: ('Overload', '2014', 'January'),
        1822: ('Overload', '2014', 'January'),
        1823: ('Overload', '2014', 'January'),

        # Article in Overload April 2010
        1623: ('Overload', '2010', 'April'),
        }
    article = json.load(f)
    res = dict()
    for s in ['id', 'title', 'body', 'date']:
        if s in article:
            res[s.capitalize()] = str(article[s]).replace('\r', '')
    if res['Title']:
        res['Title'] = res['Title'].replace('\n', ' ')
    # Some old summaries are HTML. Don't include them, but prepend to the
    # body instead. Formatting can be fixed up manually if necessary.
    if 'summary' in article and article['summary']:
        if article['summary'][0] == '<':
            res['Body'] = article['summary'] + '\n' + article['body']
        else:
            res['Note'] = article['summary']
    if not 'Note' in res:
        res['Note'] = ''
    if 'author' in article:
        name = article['author']
        if name:
            if bib_author_name_format:
                # Turn 'Fred Bloggs' into 'Bloggs, Fred'.
                np = name.rpartition(' ')
                res['Author'] = '{}, {}'.format(np[2], np[0])
            else:
                res['Author'] = name
    if not 'Author' in res:
        res['Author'] = ''
    # Although there could be more than one category apart from
    # the article category and the journal ID, in practice there isn't.
    for cid in article['category-id']:
        match = issue_re.search(cid)
        if not match:
            res['CategoryID'] = cid
    for cname in article['category-name']:
        match = journal_re.search(cname)
        if match:
            res['Journal'] = match.group('name')
            res['Year'] = match.group('year')
            # Older articles have 3 letter month abbreviations.
            res['Month'] = month_abbrev[match.group('month')[0:3]]
        else:
            res['CategoryName'] = cname
    if article['id'] in id_fixups:
        fixup = id_fixups[article['id']]
        res['Journal'] = fixup[0]
        res['Year'] = fixup[1]
        res['Month'] = fixup[2]
    return res
