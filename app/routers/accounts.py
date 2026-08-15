from fastapi import APIRouter, Depends, HTTPException
import oracledb
from typing import Optional, List
from app.database import get_connection
from app.models.schemas import AccountCreate, AccountResponse
from app.repositories.account_repository import AccountNotFoundError, InvalidStateError
from app.services.account_service import AccountService
from app.models.schemas import (
    AccountCreate, AccountResponse, ModificationRequest, RequestResponse, RejectRequest,ClosureRequest,
    HistoryEntry, ClientMasterEntry
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])

@router.post("", response_model=AccountResponse, status_code=201)
def create_account(
    data: AccountCreate,
    connection: oracledb.Connection = Depends(get_connection),
):
    service = AccountService(connection)
    try:
        return service.create_account(data)
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{account_id}/modify", response_model=RequestResponse, status_code=201)
def submit_modification(
    account_id: int,
    data: ModificationRequest,
    connection: oracledb.Connection = Depends(get_connection),
):
    service = AccountService(connection)
    try:
        return service.submit_modification(account_id, data)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/requests/{request_id}/approve")
def approve_request(request_id: int, connection: oracledb.Connection = Depends(get_connection)):
    service = AccountService(connection)
    try:
        return service.approve_modification(request_id)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/requests/{request_id}/reject")
def reject_request(
    request_id: int,
    data: RejectRequest,
    connection: oracledb.Connection = Depends(get_connection),
):
    service = AccountService(connection)
    try:
        return service.reject_modification(request_id, data.reason)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{account_id}/close", response_model=RequestResponse, status_code=201)
def submit_closure(
    account_id: int,
    data: ClosureRequest,
    connection: oracledb.Connection = Depends(get_connection),
):
    service = AccountService(connection)
    try:
        return service.submit_closure(account_id, data.reason)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/requests/{request_id}/approve-close")
def approve_closure(request_id: int, connection: oracledb.Connection = Depends(get_connection)):
    service = AccountService(connection)
    try:
        return service.approve_closure(request_id)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/requests/{request_id}/reject-close")
def reject_closure(
    request_id: int,
    data: RejectRequest,
    connection: oracledb.Connection = Depends(get_connection),
):
    service = AccountService(connection)
    try:
        return service.reject_closure(request_id, data.reason)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{account_id}/history", response_model=List[HistoryEntry])
def get_account_history(account_id: int, connection: oracledb.Connection = Depends(get_connection)):
    service = AccountService(connection)
    return service.get_account_history(account_id)


@router.get("/reports/client-master", response_model=List[ClientMasterEntry])
def client_master_report(
    status: Optional[str] = None,
    connection: oracledb.Connection = Depends(get_connection),
):
    service = AccountService(connection)
    return service.get_client_master_report(status)