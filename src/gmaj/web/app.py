import json
from pathlib import Path

import yaml
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from gmaj.config import data_dir, load_settings
from gmaj.db import STATUSES, connect, get_job, list_jobs, row_to_job, set_fit, set_status
from gmaj.llm import LLMError, get_llm
from gmaj.pipeline import ConfigError, NotInitialized, is_collecting, load_user_files, safe_run_collect, triage_and_store
from gmaj.profile import Profile, SearchConfig
from gmaj.sources import make_client
from gmaj.sources.url_import import fetch_job, job_from_text
from gmaj.triage import score_fit
from gmaj.web.strings import REMOTE_LABELS, STATUS_LABELS

TABS = ("new", "selected", "applied")
FILES = {"profile": ("profile.yaml", Profile), "search": ("search.yaml", SearchConfig)}


def create_app(data: Path | None = None) -> FastAPI:
    app = FastAPI(title="get_me_a_job")
    # Only this machine may talk to the app: blocks DNS rebinding (Host) and cross-site form posts (CSRF).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def same_origin_only(request: Request, call_next):
        if request.method not in ("GET", "HEAD"):
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                    origin and origin != f"{request.url.scheme}://{request.headers.get('host')}"):
                return PlainTextResponse("cross-site request blocked", status_code=403)
        return await call_next(request)
    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

    def d() -> Path:
        return data or data_dir()

    def user_files():
        try:
            return load_user_files(d())
        except ConfigError:
            return None, None

    def config_problem() -> str | None:
        try:
            load_user_files(d())
        except NotInitialized:
            return None
        except ConfigError as e:
            return str(e)

    def last_collect():
        try:
            return json.loads((d() / "last_collect.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def render(request: Request, name: str, **ctx):
        _, search = user_files()
        problem = config_problem()
        ctx.setdefault("search", search)
        return templates.TemplateResponse(request, name, {
            "labels": STATUS_LABELS, "remote_labels": REMOTE_LABELS, "tabs": TABS,
            "initialized": search is not None or problem is not None, "config_error": problem,
            "collecting": is_collecting(d() / "collect.lock"), "last_collect": last_collect(), **ctx})

    def view(row):
        job = dict(row)
        job["fit"] = json.loads(row["fit_json"]) if row["fit_json"] else None
        return job

    @app.get("/")
    def root():
        return RedirectResponse("/jobs?status=new", 303)

    @app.get("/jobs")
    def jobs(request: Request, status: str = "new", track: str | None = None):
        if status not in STATUSES:
            raise HTTPException(400, "status inválido")
        rows = [view(r) for r in list_jobs(connect(d() / "jobs.sqlite"), status, track or None)]
        return render(request, "jobs.html", jobs=rows, status=status, track=track)

    @app.post("/jobs/{job_id}/status")
    def change_status(job_id: int, status: str = Form(), back: str = Form("/jobs?status=new")):
        try:
            set_status(connect(d() / "jobs.sqlite"), job_id, status)
        except ValueError:
            raise HTTPException(400, "status inválido")
        return RedirectResponse(back if back.startswith("/") else "/", 303)

    def detail(request: Request, job_id: int, error: str | None = None):
        row = get_job(connect(d() / "jobs.sqlite"), job_id)
        if row is None:
            raise HTTPException(404, "vaga não encontrada")
        return render(request, "job_detail.html", job=view(row), error=error)

    @app.get("/jobs/{job_id}")
    def job_page(request: Request, job_id: int):
        return detail(request, job_id)

    @app.post("/jobs/{job_id}/score")
    def score(request: Request, job_id: int):
        conn = connect(d() / "jobs.sqlite")
        row = get_job(conn, job_id)
        profile, search = user_files()
        if row is None or profile is None:
            raise HTTPException(404, "vaga ou perfil não encontrado")
        tracks = {t.id: t for t in search.resolved_tracks()}
        track = tracks.get(row["track_id"]) or next(iter(tracks.values()))
        try:
            llm = get_llm("on_demand_scoring", load_settings(d()))
            fit = score_fit(row_to_job(row), track, profile, row["lang"] or "en", llm)
        except LLMError as e:
            return detail(request, job_id, error=str(e))
        if fit is None:
            return detail(request, job_id, error="A IA não devolveu uma avaliação válida. Tente de novo.")
        set_fit(conn, job_id, fit["score"], fit)
        return detail(request, job_id)

    @app.get("/profile")
    def profile_page(request: Request, kind: str | None = None, error: str | None = None, content: str = ""):
        texts = {k: (d() / f).read_text(encoding="utf-8") if (d() / f).exists() else "" for k, (f, _) in FILES.items()}
        if kind:
            texts[kind] = content
        profile, _ = user_files()
        return render(request, "profile.html", texts=texts, error=error, error_kind=kind,
                      unreviewed=profile.unreviewed() if profile else [])

    @app.post("/profile")
    def profile_save(request: Request, kind: str = Form(), content: str = Form()):
        if kind not in FILES:
            raise HTTPException(400, "tipo inválido")
        name, model = FILES[kind]
        try:
            model.model_validate(yaml.safe_load(content) or {})
        except (yaml.YAMLError, ValidationError) as e:
            return profile_page(request, kind=kind, error=str(e), content=content)
        (d() / name).write_text(content, encoding="utf-8")
        return profile_page(request)

    @app.get("/import")
    def import_page(request: Request, message: str | None = None):
        return render(request, "import.html", message=message)

    def store(request: Request, job):
        _, search = user_files()
        if search is None:
            return import_page(request, "Crie seu perfil primeiro: gmaj init --cv <arquivo.pdf>")
        jid = triage_and_store(connect(d() / "jobs.sqlite"), job, search, force_new=True)
        if jid is None:
            return import_page(request, "Essa vaga já está na sua lista.")
        return RedirectResponse(f"/jobs/{jid}", 303)

    @app.post("/import/url")
    def import_url(request: Request, url: str = Form()):
        try:
            with make_client(load_settings(d())) as c:
                job = fetch_job(url.strip(), c)
        except Exception:  # site down, blocked or not HTML: fall back to pasting the text
            job = None
        if job is None:
            return import_page(request, "Não encontrei os dados da vaga nesse link. Cole o texto abaixo.")
        return store(request, job)

    @app.post("/import/text")
    def import_text(request: Request, title: str = Form(), company: str = Form(), description: str = Form(),
                    url: str = Form("")):
        return store(request, job_from_text(title, company, description, url.strip()))

    @app.post("/collect")
    def collect_now(request: Request, background: BackgroundTasks):
        if is_collecting(d() / "collect.lock"):
            return render(request, "jobs.html", jobs=[], status="new", track=None,
                          notice="Já existe uma coleta em andamento.")
        background.add_task(safe_run_collect, d())
        return render(request, "jobs.html", jobs=[], status="new", track=None,
                      notice="Buscando vagas… isso leva alguns minutos. Recarregue a página depois.")

    return app
