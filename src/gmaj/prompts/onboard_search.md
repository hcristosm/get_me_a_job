Design a job search for this candidate. Split it into 1 to 4 "tracks": distinct kinds of job they could get (e.g. a technical specialty, a data/tech variant of it, an international variant).

For each track:
- "keywords": 8-15 terms in BOTH Portuguese and English that appear in matching job ads, weighted 1-3 (3 = core).
- "queries": 3-6 short job-title searches (PT and EN) for search-based sources.
- "exclude": title words that rule a job out (e.g. internship words if the candidate is experienced).
- "sources": pick from {sources}. Use "gupy" for Brazilian jobs, "reliefweb" for international humanitarian/disaster jobs; board sources (greenhouse, lever, ashby) need company slugs in "companies" — leave them out unless you are sure of a slug.
- "emphasis": ids from the profile (the [ids] below) that matter most for this track.
Set top-level "locations" from where the candidate lives (lowercase, no accents) and "exclude" for terms that apply to all tracks.

Answer with ONE JSON object that validates against this JSON schema:
{schema}

CANDIDATE PROFILE:
{profile}
