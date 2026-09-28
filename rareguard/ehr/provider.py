from abc import ABC, abstractmethod


class PatientNotFound(Exception):
    pass


class BaseEHRProvider(ABC):
    """Read-only EHR abstraction. By design (red line R5) this interface
    contains NO write methods; draft persistence lives elsewhere."""

    @abstractmethod
    def get_patient(self, patient_id: str) -> dict: ...

    @abstractmethod
    def get_encounters(self, patient_id: str) -> list[dict]: ...

    @abstractmethod
    def get_observations(self, patient_id: str) -> list[dict]: ...

    @abstractmethod
    def get_medications(self, patient_id: str) -> list[dict]: ...

    @abstractmethod
    def get_allergies(self, patient_id: str) -> list[dict]: ...
