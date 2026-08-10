from fastapi import APIRouter, Depends, HTTPException
import oracledb
from app.database import get_connection
from app.models.schemas import AccountCreate, AccountResponse
from app.services.account_service import AccountService

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