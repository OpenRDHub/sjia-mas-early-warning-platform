"""家庭端 API：建档 / 每日打卡 / 化验单上传 / 风险查询+叙述。

本模块是仅有的 HTTP 装配层；风险结论仍由确定性规则引擎给出，
LLM 只在叙述层出现且强制过六层管道（narrate 内部保证）。
"""
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from rareguard.analysis.mas import assess_patient
from rareguard.analysis.normalize import normalize
from rareguard.api.summary import latest_labs, render_summary_html
from rareguard.ingest.ocr import commit_confirmed, parse_dual
from rareguard.narrate import narrate
from rareguard.ts.provider import SqliteTimeSeries


class PatientIn(BaseModel):
    pid: str
    name: str
    dob: str


class CheckinIn(BaseModel):
    pid: str
    date: str
    temp: float
    symptoms: dict = {}


class LabUploadIn(BaseModel):
    pid: str
    date: str
    image_b64: str


class ManualLabItem(BaseModel):
    name: str
    value: float
    unit: str = ""
    ref_low: float | None = None
    ref_high: float | None = None


class ManualLabIn(BaseModel):
    pid: str
    date: str
    items: list[ManualLabItem]


def create_home_app(store, ocr_provider, narrate_provider) -> FastAPI:
    app = FastAPI(title="RareGuard 家庭端")
    ts = SqliteTimeSeries(store)

    @app.post("/api/home/patients", status_code=201)
    def add_patient(body: PatientIn):
        store.add_patient(body.pid, body.name, body.dob)
        return {"ok": True}

    @app.post("/api/home/checkin")
    def checkin(body: CheckinIn):
        store.add_checkin(body.pid, body.date, body.temp, body.symptoms)
        return {"ok": True}

    @app.post("/api/home/labs/upload")
    def upload_lab(body: LabUploadIn):
        try:
            items = parse_dual(body.image_b64, ocr_provider)
        except Exception:
            # OCR 不可用 → 前端转结构化手工录入表单兜底（spec §2 降级路径）
            return {"items": [], "committed": 0, "ocr_error": "unavailable"}
        committed = commit_confirmed(store, body.pid, body.date, items)
        return {"items": items, "committed": committed}

    @app.post("/api/home/labs/manual")
    def manual_lab(body: ManualLabIn):
        results = []
        for item in body.items:
            try:
                code, value = normalize(item.name, item.value, item.unit)
            except Exception as exc:
                results.append({"name": item.name, "code": None,
                                "ok": False, "reason": type(exc).__name__})
                continue
            store.add_lab(body.pid, body.date, code, value,
                          item.ref_low, item.ref_high, source="manual")
            results.append({"name": item.name, "code": code,
                            "ok": True, "reason": ""})
        return {"results": results}

    @app.get("/api/home/trend/{pid}")
    def trend(pid: str, as_of: str, days: int = 90):
        start = date.fromisoformat(as_of) - timedelta(days=days - 1)
        points = []
        for offset in range(days):
            day = (start + timedelta(days=offset)).isoformat()
            a = assess_patient(ts, pid, day)
            points.append({"date": day, "score": a.score, "level": a.level})
        return {"points": points}

    @app.get("/api/home/risk/{pid}")
    def risk(pid: str, as_of: str):
        assessment = assess_patient(ts, pid, as_of)
        text, meta = narrate(assessment, narrate_provider,
                             trace_id=f"home-{pid}-{as_of}")
        return {"level": assessment.level, "score": assessment.score,
                "hits": [{"rule_id": h.rule_id, "name": h.name,
                          "level": h.level} for h in assessment.hits],
                "text": text, "meta": meta}

    @app.get("/api/home/summary/{pid}")
    def summary(pid: str, as_of: str):
        assessment = assess_patient(ts, pid, as_of)
        prow = store.rows("SELECT name FROM patient WHERE pid=?", (pid,))
        name = prow[0][0] if prow else pid
        start = date.fromisoformat(as_of) - timedelta(days=89)
        points = [{"date": (start + timedelta(days=o)).isoformat(),
                   "score": assess_patient(ts, pid,
                       (start + timedelta(days=o)).isoformat()).score}
                  for o in range(90)]
        return HTMLResponse(render_summary_html(
            pid, name, as_of, assessment.level, assessment.score,
            [{"name": h.name, "level": h.level} for h in assessment.hits],
            points, latest_labs(store, pid, as_of)))

    return app
