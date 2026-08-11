from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional
import re


class ClientCreate(BaseModel):
    pan_number: str = Field(..., min_length=10, max_length=10)
    full_name: str = Field(..., min_length=1, max_length=150)
    dob: Optional[date] = None
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=50)
    pincode: Optional[str] = Field(None, max_length=10)
    email: Optional[str] = Field(None, max_length=100)
    mobile: Optional[str] = Field(None, max_length=15)

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        v = v.upper().strip()
        if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", v):
            raise ValueError("PAN must be in format AAAAA9999A")
        return v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[6-9]\d{9}$", v):
            raise ValueError("Mobile number must be a valid 10-digit Indian number")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format")
        return v


class AccountCreate(BaseModel):
    dp_id: str = Field(..., min_length=8, max_length=8)
    client: ClientCreate
    nominee_name: Optional[str] = Field(None, max_length=150)
    bank_account_no: Optional[str] = Field(None, max_length=30)
    bank_ifsc: Optional[str] = Field(None, max_length=15)

    @field_validator("bank_ifsc")
    @classmethod
    def validate_ifsc(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", v.upper()):
            raise ValueError("Invalid IFSC format")
        return v.upper() if v else v


class AccountResponse(BaseModel):
    account_id: int
    dp_id: str
    client_id: int
    account_status: str
    nominee_name: Optional[str]
    opened_date: date

    class Config:
        from_attributes = True

class ModificationRequest(BaseModel):
    nominee_name: Optional[str] = Field(None, max_length=150)
    bank_account_no: Optional[str] = Field(None, max_length=30)
    bank_ifsc: Optional[str] = Field(None, max_length=15)
    address_line1: Optional[str] = Field(None, max_length=200)
    address_line2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=50)
    pincode: Optional[str] = Field(None, max_length=10)
    mobile: Optional[str] = Field(None, max_length=15)
    email: Optional[str] = Field(None, max_length=100)

    @field_validator("bank_ifsc")
    @classmethod
    def validate_ifsc(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", v.upper()):
            raise ValueError("Invalid IFSC format")
        return v.upper() if v else v

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[6-9]\d{9}$", v):
            raise ValueError("Mobile number must be a valid 10-digit Indian number")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format")
        return v

    def changed_fields(self) -> dict:
        return self.model_dump(exclude_unset=True, exclude_none=True)

class RequestResponse(BaseModel):
    request_id: int
    account_id: Optional[int] = None
    request_type: str
    request_status: str
    requested_at: date

    class Config:
        from_attributes = True

class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)