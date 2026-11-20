Turn this CV into a structured, bilingual master profile.

Rules:
- Copy facts exactly. Never invent experiences, numbers, dates, tools or results that are not in the CV.
- Every text field (objects with "pt"/"en") must have BOTH a Portuguese ("pt") and an English ("en") version.
- Set "canonical_lang" to the CV's language. The other language is your translation: list it in that field's "auto" array (e.g. "auto": ["en"]).
- Give every experience, bullet, education, project, award, course and skill group a short unique "id" (exp-1, exp-1-b1, edu-1, prj-1, awd-1, crs-1, sk-1 ...).
- Keep each CV bullet as one bullet. Put contact links (LinkedIn, GitHub, site) in "links".
- Leave "answers" empty.

Answer with ONE JSON object that validates against this JSON schema:
{schema}

CV TEXT:
{cv_text}
