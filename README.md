# get_me_a_job

A local tool that finds jobs in **your** niche, scores how well each one fits your profile, and keeps a short, ranked list you can act on. It runs on your machine, uses free local AI for the bulk work and your existing Claude subscription only where writing quality matters.

> Português: veja [a seção em português](#português) abaixo.

**What it does (phase 1)**

- **Master profile from your CV**: `gmaj init --cv cv.pdf` turns your CV into a bilingual (PT/EN) profile plus suggested search *tracks*.
- **Tracks**: each kind of job you look for (e.g. "geotechnics", "GIS & data") has its own keywords, exclusions, locations and sources. Every job is scored against the track it fits best.
- **Collect on demand**: one click on **Buscar vagas** pulls jobs from public job APIs (Gupy, Greenhouse, Lever, Ashby, ReliefWeb), drops duplicates, filters by keywords for free, then asks a local model (Ollama) for a 0–100 fit score with strengths and gaps.
- **Import anything else**: paste a job link (pages with schema.org `JobPosting` data) or the job text. LinkedIn is never scraped: paste the text instead.
- **Local web UI** to triage: new → selected → applied, plus a profile editor.

**What it never does**: submit applications, send messages, or upload your data anywhere. Everything (profile, database) lives in your user data folder, outside this repository.

## Requirements

- Python 3.12+
- Optional, for fit scores: [Ollama](https://ollama.com) with a model, e.g. `ollama pull qwen3.5:9b`
- Optional, for onboarding and on-demand scoring: [Claude Code](https://docs.claude.com/en/docs/claude-code) CLI, logged in (`claude` once) with a Pro or Max plan. No API key needed.

Without Ollama, jobs are ranked by keyword score. Without Claude Code, you can point every task at Ollama in `settings.yaml`.

## Install

```bash
git clone <this repo> && cd get_me_a_job
python3 -m venv .venv && .venv/bin/pip install -e .
```

## Quickstart

```bash
.venv/bin/gmaj init --cv path/to/your_cv.pdf   # builds profile.yaml + search.yaml
.venv/bin/gmaj install-launcher --desktop      # adds a "get_me_a_job" icon (Linux)
```

From then on, **click the get_me_a_job icon**: the dashboard opens in your browser, and the app stops by itself a few seconds after you close the tab. No terminal needed. `gmaj open` does the same from a terminal, and `gmaj serve` runs it until Ctrl+C.

In the dashboard: open **Perfil**, review the machine-translated fields and your tracks, and click **Buscar vagas**. `gmaj collect` does the same from the terminal.

### Optional: daily automatic collection

Collecting is manual by default. To run it every day at 08:00 (Linux, systemd user timer):

```bash
.venv/bin/gmaj schedule install --hour 8
.venv/bin/gmaj schedule remove             # undo
```

On systems without systemd the command prints the equivalent `crontab` line.

## Concepts

- **Data folder**: `~/.local/share/get_me_a_job/` on Linux (set `GMAJ_DATA_DIR` to change it). It holds `profile.yaml`, `search.yaml`, `settings.yaml`, `jobs.sqlite` and `last_collect.json`.
- **Bilingual text**: every free-text field has `pt` and `en`. `auto: [en]` marks an unreviewed machine translation; delete that line once you have checked it.
- **Tracks** (`search.yaml`): `keywords` (term → weight 1–3, title matches count double), `queries` (search terms for Gupy/ReliefWeb), `exclude` (title words that drop a job), `locations`, `remote`, `sources`, `companies` (board slugs per source), `emphasis` (profile ids to highlight later), `min_score`. Top-level `exclude`, `locations` and `remote` apply to every track.
- **Company boards**: Greenhouse, Lever and Ashby list jobs per company. Add the slug from the company's job page URL, e.g. `companies: {greenhouse: [planetlabs], lever: [palantir], ashby: [ramp]}`.

See [`examples/`](examples/) for a complete fictional profile and search config.

## Settings (`settings.yaml`, all optional)

```yaml
llm:
  onboarding: claude_cli          # or ollama
  scoring: ollama                 # fit scores during collect
  on_demand_scoring: claude_cli   # the "Avaliar com Claude" button
  ollama_url: http://127.0.0.1:11434
  ollama_model: qwen3.5:9b
  claude_bin: claude
  timeout_s: 300
max_scored_per_run: 30
reliefweb_appname: null           # ReliefWeb needs an approved appname
port: 8765
user_agent: get_me_a_job/0.1
```

**ReliefWeb**: the API only answers approved app names. Request one at <https://apidoc.reliefweb.int/parameters#appname> and set `reliefweb_appname`. Until then the source is skipped.

## Why LinkedIn is import-only

LinkedIn forbids automated access and bans accounts for it. Paste the job text in **Importar** instead.

## Roadmap

1. ~~Find and triage~~ (this release)
2. Tailored CV per job (never inventing anything), cover letter, short message to the hiring manager, follow-up reminders
3. Browser extension that fills repetitive application forms from your profile (you always click submit)
4. More sources (InfoJobs, Catho, FAPESP, EURAXESS), response-rate dashboard, UI translation

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Adding a job source is a small, self-contained PR.

## License

[MIT](LICENSE)

---

## Português

Ferramenta local que encontra vagas do **seu** nicho, dá uma nota de encaixe para cada uma e mantém uma lista curta e ordenada. Roda na sua máquina, usa IA local gratuita para o trabalho pesado e a sua assinatura do Claude só onde a qualidade do texto importa.

- `gmaj init --cv cv.pdf` cria um perfil bilíngue (PT/EN) e sugere **trilhas** de busca a partir do seu CV.
- O botão **Buscar vagas** coleta vagas de APIs públicas (Gupy, Greenhouse, Lever, Ashby, ReliefWeb), filtra por palavras-chave e pede ao modelo local (Ollama) uma nota de 0 a 100, com pontos fortes e lacunas.
- Vagas de outros sites entram pelo link ou colando o texto. O LinkedIn nunca é raspado.
- Nada é enviado automaticamente, e seus dados ficam na sua pasta de usuário, fora do repositório.

**Instalar e usar**

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/gmaj init --cv seu_cv.pdf
.venv/bin/gmaj install-launcher --desktop   # cria o ícone "get_me_a_job"
```

Depois é só clicar no ícone: o painel abre no navegador e o programa desliga sozinho alguns segundos depois que você fecha a aba. Revise o perfil na aba **Perfil** (apague `auto: [en]` dos campos já conferidos) e clique em **Buscar vagas**. A coleta automática diária é opcional: `gmaj schedule install`.

Requisitos opcionais: Ollama com um modelo (para as notas) e o Claude Code logado num plano Pro ou Max (para o onboarding). Sem chave de API paga.
