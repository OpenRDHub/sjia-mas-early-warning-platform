"""家庭端 API：建档 / 每日打卡 / 化验单上传 / 风险查询+叙述。

本模块是仅有的 HTTP 装配层；风险结论仍由确定性规则引擎给出，
LLM 只在叙述层出现且强制过六层管道（narrate 内部保证）。
"""
from fastapi import FastAPI
from pydantic import BaseModel

from rareguard.analysis.mas import assess_patient
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
        items = parse_dual(body.image_b64, ocr_provider)
        committed = commit_confirmed(store, body.pid, body.date, items)
        return {"items": items, "committed": committed}

    @app.get("/api/home/risk/{pid}")
    def risk(pid: str, as_of: str):
        assessment = assess_patient(ts, pid, as_of)
        text, meta = narrate(assessment, narrate_provider,
                             trace_id=f"home-{pid}-{as_of}")
        return {"level": assessment.level, "score": assessment.score,
                "hits": [{"rule_id": h.rule_id, "name": h.name,
                          "level": h.level} for h in assessment.hits],
                "text": text, "meta": meta}

    return app
