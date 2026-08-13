from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
import oracledb
from app.database import get_connection
from app.services.bulk_upload_service import BulkUploadService
from app.models.schemas import BulkUploadResponse

router = APIRouter(prefix="/bulk-upload", tags=["bulk-upload"])


@router.post("", response_model=BulkUploadResponse, status_code=201)
async def upload_accounts(
    file: UploadFile = File(...),
    connection: oracledb.Connection = Depends(get_connection),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    service = BulkUploadService(connection)
    try:
        result = service.process_file(content, file.filename)
        return BulkUploadResponse(**result)
    except oracledb.DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")