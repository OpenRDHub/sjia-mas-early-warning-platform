from rareguard.ehr.provider import BaseEHRProvider, PatientNotFound

_PATIENTS = {
    "P001": {
        "id": "P001",
        "name": "张伟",
        "gender": "男",
        "birth_date": "1958-03-12",
    },
    "P002": {
        "id": "P002",
        "name": "李芳",
        "gender": "女",
        "birth_date": "1990-07-25",
    },
}

_ENCOUNTERS = {
    "P001": [
        {"date": "2026-05-11", "dept": "心内科", "summary": "高血压复诊，血压控制欠佳"},
        {"date": "2026-02-03", "dept": "全科", "summary": "上呼吸道感染"},
    ],
    "P002": [{"date": "2026-06-20", "dept": "皮肤科", "summary": "荨麻疹"}],
}

_OBSERVATIONS = {
    "P001": [
        {"date": "2026-05-11", "type": "blood_pressure", "value": "152/95", "unit": "mmHg"},
        {"date": "2026-05-11", "type": "ldl_cholesterol", "value": 3.9, "unit": "mmol/L"},
    ],
    "P002": [],
}

_MEDICATIONS = {
    "P001": [
        {"name": "苯磺酸氨氯地平片", "dose": "5mg", "freq": "每日一次"},
        {"name": "阿司匹林肠溶片", "dose": "100mg", "freq": "每日一次"},
    ],
    "P002": [{"name": "氯雷他定片", "dose": "10mg", "freq": "每日一次"}],
}

_ALLERGIES = {
    "P001": [{"substance": "青霉素", "reaction": "皮疹", "severity": "严重"}],
    "P002": [],
}


class MockEHRProvider(BaseEHRProvider):
    def _check(self, patient_id: str) -> None:
        if patient_id not in _PATIENTS:
            raise PatientNotFound(patient_id)

    def get_patient(self, patient_id: str) -> dict:
        self._check(patient_id)
        return dict(_PATIENTS[patient_id])

    def get_encounters(self, patient_id: str) -> list[dict]:
        self._check(patient_id)
        return list(_ENCOUNTERS[patient_id])

    def get_observations(self, patient_id: str) -> list[dict]:
        self._check(patient_id)
        return list(_OBSERVATIONS[patient_id])

    def get_medications(self, patient_id: str) -> list[dict]:
        self._check(patient_id)
        return list(_MEDICATIONS[patient_id])

    def get_allergies(self, patient_id: str) -> list[dict]:
        self._check(patient_id)
        return list(_ALLERGIES[patient_id])
