import accuwebsite

adoc_header = """= Title
:author: Author
:figure-caption!:
:imagesdir: ..

[.lead]
Summary

"""

def convert(xml):
    res = accuwebsite.convert_article(xml, 'xml', 'adoc', 'Title', 'Author', summary='Summary')
    s = res[0]
    if s.startswith(adoc_header):
        s = s.replace(adoc_header, '', 1)
    return s

def test_h2():
    res = convert('<h2>heading</h2>')
    assert res == '\n== heading\n'

def test_h2():
    res = convert('<h2>References</h2>')
    assert res == '\n[bibliography]\n== References\n'

def test_h3():
    res = convert('<h3>heading</h3>')
    assert res == '\n=== heading\n'

def test_h4():
    res = convert('<h4>heading</h4>')
    assert res == '\n==== heading\n'

def test_h5():
    res = convert('<h5>heading</h5>')
    assert res == '\n===== heading\n'

def test_h6():
    res = convert('<h6>heading</h6>')
    assert res == '\n====== heading\n'

def test_p():
    res = convert('<p>text and more</p>')
    assert res == '\ntext and more'
    res = convert('<p> space then text and more</p>')
    assert res == '\nspace then text and more'

def test_p2():
    res = convert('<xml><p>text and more</p><p>and a second</p></xml>')
    assert res == '\ntext and more\n\nand a second'

def test_cite():
    res = convert('<p>text <cite>and</cite> more</p>')
    assert res == '\ntext __and__ more'

def test_em():
    res = convert('<p>text <em>and</em> more</p>')
    assert res == '\ntext __and__ more'

def test_i():
    res = convert('<p>text <i>and</i> more</p>')
    assert res == '\ntext __and__ more'

def test_u():
    res = convert('<p>text <u>and</u> more</p>')
    assert res == '\ntext __and__ more'

def test_b():
    res = convert('<p>text <b>and</b> more</p>')
    assert res == '\ntext **and** more'

def test_span():
    res = convert('<p>text <span>and</span> more</p>')
    assert res == '\ntext and more'
    res = convert('<p>text <span class="author">author2</span> more</p>')
    assert res == '\ntext author2 more'

def test_strong():
    res = convert('<p>text <strong>and</strong> more</p>')
    assert res == '\ntext **and** more'

def test_cpp():
    res = convert('<p>text C++ more</p>')
    assert res == '\ntext {cpp} more'

def test_a():
    res = convert('<p>text and <a href="link.html">Link</a> more</p>')
    assert res == '\ntext and link:link.html[Link] more'

def test_a_bib():
    res = convert('<p>text and <a id="[anid]" />more</p>')
    assert res == '\ntext and [[[refanid,anid]]] more'
    res = convert('<p>text and <a name="[anid]" />more</p>')
    assert res == '\ntext and [[[refanid,anid]]] more'
    res = convert('<p>text and <a id="anid">anchor</a> more</p>')
    assert res == '\ntext and [[refanid,anid]]anchor more'
    res = convert('<p>text and <a name="anid">anchor</a> more</p>')
    assert res == '\ntext and [[refanid,anid]]anchor more'

def test_a_bib_ref():
    res = convert('<p>text and <a href="#[link]">Link</a> more</p>')
    assert res == '\ntext and <<reflink>> more'

def test_img():
    res = convert('<img src="link.html" />')
    assert res == 'image::link.html[]\n'
    res = convert('<xml>text and <img src="link.html" /></xml>')
    assert res == 'text and \nimage::link.html[]\n'

def test_ol():
    res = convert('<ol><li>List 1</li><li>List 2</li></ol>')
    assert res == '\n. List 1\n. List 2\n'
    res = convert('<ol><li>One<ol><li>List 1</li></ol></li><li>Two<ol><li>List 2</li></ol></li></ol>')
    assert res == '\n. One\n+\n.. List 1\n. Two\n+\n.. List 2\n'

def test_ul():
    res = convert('<ul><li>List 1</li><li>List 2</li></ul>')
    assert res == '\n* List 1\n* List 2\n'

def test_li():
    res = convert('<ul><li><p>List 1</p></li><li>List 2</li></ul>')
    assert res == '\n* List 1\n* List 2\n'
    res = convert('<ul><li>\n<p>List 1</p>\n<p>List 1 cont</p></li><li>List 2</li></ul>')
    assert res == '\n* List 1 \n+\nList 1 cont\n* List 2\n'

def test_dddt():
    res = convert('<xml><dt>Def</dt>\n<dd>The definition</dd></xml>')
    assert res == '\nDef:: \nThe definition'

def test_table():
    res = convert('<table></table')
    assert res == '\n[separator=¦]\n|===\n\n|===\n'

def test_bf():
    res = convert('<p>This is<br> a second line</p>')
    assert res == '\nThis is +\na second line'
