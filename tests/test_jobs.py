from gmaj.jobs import Job, dedup_key, html_to_text, normalize


def test_normalize_strips_accents():
    assert normalize("  Geólogo   Sênior ") == "geologo senior"


def test_dedup_key_ignores_case_and_accents():
    a = Job("gupy", "1", "u1", "Geólogo Pleno", "Acme")
    b = Job("greenhouse", "9", "u2", "geologo pleno", "ACME ")
    assert dedup_key(a) == dedup_key(b)


def test_html_to_text_unescapes_and_breaks_blocks():
    assert html_to_text("&lt;p&gt;Taludes &amp; encostas&lt;/p&gt;&lt;li&gt;QGIS&lt;/li&gt;") == "Taludes & encostas\nQGIS"


def test_html_to_text_plain_html():
    assert html_to_text("<div>A<br>B</div><p></p><p></p><p>C</p>") == "A\nB\n\nC"
