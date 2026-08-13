import csv
import io
from pydantic import ValidationError
from app.models.schemas import BulkUploadRow
from app.repositories.account_repository import AccountRepository

class BulkUploadService:
    def __init__(self, connection):
        self.conn = connection
        self.repository = AccountRepository(connection)

    def process_file(self, file_content: bytes, file_name: str) -> dict:
        text = file_content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        valid_rows = []
        invalid_rows = []

        for i, raw_row in enumerate(reader, start=1):
            try:
                validated = BulkUploadRow(**raw_row)
                valid_rows.append(validated)
            except ValidationError as e:
                invalid_rows.append((i, str(raw_row), str(e)))

        batch_id = self.repository.create_upload_batch(
            file_name, total = len(valid_rows) + len(invalid_rows))

        inserted_count = 0
        if valid_rows:
            inserted_count = self.repository.bulk_insert_accounts(valid_rows, batch_id)
        if invalid_rows:
            self.repository.log_upload_errors(batch_id,invalid_rows)

        status = "COMPLETED" if not invalid_rows else (
            "COMPLETED_WITH_ERRORS" if inserted_count > 0 else "FAILED"
        )
        self.repository.finalize_batch(batch_id, inserted_count, len(invalid_rows), status)

        return {
            "batch_id": batch_id,
            "total_records": len(valid_rows) + len(invalid_rows),
            "success_count": inserted_count,
            "error_count": len(invalid_rows),
            "batch_status": status,
        }
