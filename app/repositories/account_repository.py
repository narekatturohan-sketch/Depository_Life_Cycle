import oracledb
import json
from datetime import datetime
from app.models.schemas import AccountCreate
import traceback


class DuplicatePanError(Exception):
    pass


class AccountRepository:
    def __init__(self, connection: oracledb.Connection):
        self.conn = connection

    def create_account(self, data: AccountCreate) -> dict:
        """
        Creates a client (if new) and a demat account in one transaction.
        Uses SELECT FOR UPDATE to safely check PAN uniqueness without a race
        condition between the check and the insert.
        """
        cursor = self.conn.cursor()
        try:
            # --- DB-dependent check: PAN uniqueness, row-locked ---
            cursor.execute(
                "SELECT client_id FROM clients WHERE pan_number = :pan FOR UPDATE",
                pan=data.client.pan_number,
            )
            existing = cursor.fetchone()

            if existing:
                client_id = existing[0]
            else:
                client_id_var = cursor.var(int)
                cursor.execute(
                    """
                    INSERT INTO clients (
                        pan_number, full_name, dob, address_line1, address_line2,
                        city, state, pincode, email, mobile
                    ) VALUES (
                        :pan, :full_name, :dob, :addr1, :addr2,
                        :city, :state, :pincode, :email, :mobile
                    )
                    RETURNING client_id INTO :client_id
                    """,
                    pan=data.client.pan_number,
                    full_name=data.client.full_name,
                    dob=data.client.dob,
                    addr1=data.client.address_line1,
                    addr2=data.client.address_line2,
                    city=data.client.city,
                    state=data.client.state,
                    pincode=data.client.pincode,
                    email=data.client.email,
                    mobile=data.client.mobile,
                    client_id=client_id_var,
                )
                client_id = client_id_var.getvalue()[0]

            # --- Insert the demat account, linked to the client ---
            account_id_var = cursor.var(int)
            cursor.execute(
                """
                INSERT INTO demat_accounts (
                    dp_id, client_id, nominee_name, bank_account_no, bank_ifsc
                ) VALUES (
                    :dp_id, :client_id, :nominee_name, :bank_account_no, :bank_ifsc
                )
                RETURNING account_id INTO :account_id
                """,
                dp_id=data.dp_id,
                client_id=client_id,
                nominee_name=data.nominee_name,
                bank_account_no=data.bank_account_no,
                bank_ifsc=data.bank_ifsc,
                account_id=account_id_var,
            )
            account_id = account_id_var.getvalue()[0]

            # --- Log to history (append-only audit trail) ---
            cursor.execute(
                """
                INSERT INTO account_history (
                    account_id, field_changed, old_value, new_value, changed_by
                ) VALUES (
                    :account_id, 'ACCOUNT_CREATED', NULL, 'ACTIVE', 'SYSTEM'
                )
                """,
                account_id=account_id,
            )

            self.conn.commit()

            cursor.execute(
                """
                SELECT account_id, dp_id, client_id, account_status,
                       nominee_name, opened_date
                FROM demat_accounts WHERE account_id = :id
                """,
                id=account_id,
            )
            row = cursor.fetchone()
            return {
                "account_id": row[0],
                "dp_id": row[1],
                "client_id": row[2],
                "account_status": row[3],
                "nominee_name": row[4],
                "opened_date": row[5].date() if row[5] else None,
            }

        except oracledb.DatabaseError:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def submit_modification(self, account_id: int, changes: dict) -> dict:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT account_status FROM demat_accounts WHERE account_id = :id for UPDATE",
                id=account_id,
            )
            row = cursor.fetchone()
            if not row:
                raise AccountNotFoundError(f"Account ID {account_id} not found.")
            else:
                if row[0] != "ACTIVE":
                    raise InvalidStateError(
                        f"Cannot modify account in state {row[0]}."
                    )

            request_id_var = cursor.var(int)
            cursor.execute(
                """
                INSERT into account_requests
                (
                    account_id,
                    request_type,
                    request_payload,
                    request_status
                )
                VALUES
                (
                    :account_id,
                    'MODIFY',
                    :payload,
                    'PENDING'
                )
                RETURNING request_id INTO :request_id
                """,
                account_id=account_id,
                payload=json.dumps(changes),
                request_id=request_id_var,
            )
            request_id = request_id_var.getvalue()[0]

            cursor.execute(
                """
                UPDATE demat_accounts
                SET account_status = 'MODIFICATION_PENDING',
                updated_at = SYSTIMESTAMP
                WHERE account_id = :id
                """,
                id=account_id
            )

            self.conn.commit()
            return {"request_id": request_id, "account_id": account_id, 
                    "request_type": "MODIFY", "request_status": "PENDING",
                    "requested_at": datetime.now().isoformat()}

        except oracledb.DatabaseError:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def approve_modification(self, request_id: int) -> dict:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT account_id, request_type, request_payload," \
                "request_status FROM account_requests WHERE request_id = :id for UPDATE",
                id=request_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise AccountNotFoundError(f"Request ID {request_id} not found.")

            account_id, request_type, request_payload, request_status = row
            if request_status != "PENDING":
                raise InvalidStateError(
                    f"Cannot approve request in state {request_status}."
                )
            if request_type != "MODIFY":
                raise InvalidStateError(
                    f"Cannot approve request of type {request_type}."
                )

            changes = json.loads(request_payload.read() if hasattr(request_payload, "read") else request_payload)

            allowed_fields = {"nominee_name", "bank_account_no", "bank_ifsc"}
            client_fields = {"address_line1", "address_line2", "city", "state", "pincode", "mobile", "email"}

            cursor.execute(
                "SELECT client_id, nominee_name, bank_account_no, bank_ifsc "
                "FROM demat_accounts WHERE account_id = :id for UPDATE",
                id=account_id,
            )
            acc_row = cursor.fetchone()
            client_id = acc_row[0]
            current_account_status = {
                "nominee_name": acc_row[1],
                "bank_account_no": acc_row[2],
                "bank_ifsc": acc_row[3],
            }

            for field, new_value in changes.items():
                if field in allowed_fields:
                    old_value = current_account_status.get(field)
                    if old_value != new_value:
                        cursor.execute(
                            f"UPDATE demat_accounts SET {field} = :new_value, updated_at = SYSTIMESTAMP WHERE account_id = :id",
                            new_value=new_value,
                            id=account_id,
                        )
                        cursor.execute(
                            f"""INSERT INTO account_history
                            (
                                account_id, request_id, field_changed, old_value, new_value, changed_by
                            ) VALUES (:account_id, :request_id, :field_changed, :old_value, :new_value, 'SYSTEM')""",
                            account_id=account_id,
                            request_id=request_id,
                            field_changed=field,
                            old_value=old_value,
                            new_value=new_value,
                        )
                elif field in client_fields:
                    cursor.execute(
                        f"SELECT {field} FROM clients WHERE client_id = :id for UPDATE",
                        id=client_id,
                    )
                    client_row = cursor.fetchone()
                    old_value = client_row[0]
                    if old_value != new_value:
                        cursor.execute(
                            f"""UPDATE clients 
                            SET {field} = :new_value,
                            updated_at = SYSTIMESTAMP
                            WHERE client_id = :id""",
                            new_value=new_value,
                            id=client_id,
                        )
                        cursor.execute(
                            f"""INSERT INTO account_history
                            (
                                account_id, request_id, field_changed, old_value, new_value, changed_by
                            ) VALUES (:account_id, :request_id, :field_changed, :old_value, :new_value, 'SYSTEM')""",
                            account_id=account_id,
                            request_id=request_id,
                            field_changed=field,
                            old_value=old_value,
                            new_value=new_value,
                        )

            cursor.execute(
                "UPDATE account_requests SET request_status = 'APPROVED', "
                "resolved_at = SYSTIMESTAMP WHERE request_id = :id",
                id=request_id,
            )
            cursor.execute(
                "UPDATE demat_accounts SET account_status = 'ACTIVE', "
                "updated_at = SYSTIMESTAMP WHERE account_id = :id",
                id=account_id,
            )

            self.conn.commit()
            return {"request_id": request_id, "status": "APPROVED", "account_id": account_id}
        except (oracledb.DatabaseError, AccountNotFoundError, InvalidStateError):
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def reject_modification(self, request_id: int, reason: str) -> dict:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT account_id, request_status FROM account_requests "
                "WHERE request_id = :id FOR UPDATE",
                id=request_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise AccountNotFoundError(f"Request {request_id} not found")
            account_id, status = row
            if status != "PENDING":
                raise InvalidStateError(f"Request is {status}, must be PENDING")

            cursor.execute(
                "UPDATE account_requests SET request_status = 'REJECTED', "
                "rejection_reason = :reason, resolved_at = SYSTIMESTAMP "
                "WHERE request_id = :id",
                reason=reason, id=request_id,
            )
            cursor.execute(
                "UPDATE demat_accounts SET account_status = 'ACTIVE', "
                "updated_at = SYSTIMESTAMP WHERE account_id = :id",
                id=account_id,
            )

            self.conn.commit()
            return {"request_id": request_id, "status": "REJECTED", "account_id": account_id}
        except (oracledb.DatabaseError, AccountNotFoundError, InvalidStateError):
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def submit_closure(self, account_id:int, reason:str) -> dict:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """SELECT account_status FROM demat_accounts WHERE account_id = :id for UPDATE""",
                id=account_id,
            )
            row = cursor.fetchone()
            if not row:
                raise AccountNotFoundError(f"Account ID {account_id} not Found.")
            else:
                if row[0] != "ACTIVE":
                    raise InvalidStateError(f"Account is in state {row[0]}, must be ACTIVE to submit closure request.")

            request_id_var = cursor.var(int)

            cursor.execute(
                """
                INSERT INTO account_requests (
                    account_id, request_type, request_payload, request_status
                ) VALUES (
                    :account_id, 'CLOSE', :payload, 'PENDING'
                )
                RETURNING request_id INTO :request_id
                """,
                account_id=account_id,
                payload=json.dumps({"reason": reason}),
                request_id=request_id_var,
            )
            request_id = request_id_var.getvalue()[0]

            cursor.execute("""
                UPDATE demat_accounts
                SET account_status = 'CLOSURE_PENDING', updated_at = SYSTIMESTAMP
                WHERE account_id = :id
                """,
                id=account_id,
            )

            self.conn.commit()
            return {"request_id": request_id, "account_id": account_id,
                     "request_type": "CLOSE", "request_status": "PENDING",
                     "requested_at": datetime.now().isoformat()}
        except (oracledb.DatabaseError, AccountNotFoundError, InvalidStateError):
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def approve_closure(self, request_id: int) -> dict:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT account_id, request_type, request_status "
                "FROM account_requests WHERE request_id = :id FOR UPDATE",
                id=request_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise AccountNotFoundError(f"Request {request_id} not found")
            account_id, request_type, status = row
            if status != "PENDING":
                raise InvalidStateError(f"Request is {status}, must be PENDING")
            if request_type != "CLOSE":
                raise InvalidStateError(f"Request type is {request_type}, not CLOSE")

            cursor.execute(
                "UPDATE demat_accounts SET account_status = 'CLOSED', "
                "closed_date = SYSDATE, updated_at = SYSTIMESTAMP "
                "WHERE account_id = :id",
                id=account_id,
            )
            cursor.execute(
                """
                INSERT INTO account_history (
                    account_id, request_id, field_changed, old_value, new_value, changed_by
                ) VALUES (:acc_id, :req_id, 'ACCOUNT_STATUS', 'ACTIVE', 'CLOSED', 'SYSTEM')
                """,
                acc_id=account_id, req_id=request_id,
            )
            cursor.execute(
                "UPDATE account_requests SET request_status = 'APPROVED', "
                "resolved_at = SYSTIMESTAMP WHERE request_id = :id",
                id=request_id,
            )

            self.conn.commit()
            return {"request_id": request_id, "status": "APPROVED", "account_id": account_id}
        except (oracledb.DatabaseError, AccountNotFoundError, InvalidStateError):
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def reject_closure(self, request_id: int, reason: str) -> dict:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT account_id, request_type, request_status "
                "FROM account_requests WHERE request_id = :id FOR UPDATE",
                id=request_id,
            )
            row = cursor.fetchone()
            if row is None:
                raise AccountNotFoundError(f"Request {request_id} not found")
            account_id, request_type, status = row
            if status != "PENDING":
                raise InvalidStateError(f"Request is {status}, must be PENDING")
            if request_type != "CLOSE":
                raise InvalidStateError(f"Request type is {request_type}, not CLOSE")

            cursor.execute(
                "UPDATE account_requests SET request_status = 'REJECTED', "
                "rejection_reason = :reason, resolved_at = SYSTIMESTAMP "
                "WHERE request_id = :id",
                reason=reason, id=request_id,
            )
            cursor.execute(
                "UPDATE demat_accounts SET account_status = 'ACTIVE', "
                "updated_at = SYSTIMESTAMP WHERE account_id = :id",
                id=account_id,
            )

            self.conn.commit()
            return {"request_id": request_id, "status": "REJECTED", "account_id": account_id}
        except (oracledb.DatabaseError, AccountNotFoundError, InvalidStateError):
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def create_upload_batch(self, filename: str, total: int) -> int:
        cursor = self.conn.cursor()
        try:
            batch_id_var = cursor.var(int)
            cursor.execute(
                """
                INSERT INTO bulk_upload_batches (
                    file_name,
                    total_records,
                    batch_status
                )
                VALUES (
                    :filename,
                    :total,
                    'PROCESSING'
                )
                RETURNING batch_id INTO :batch_id
                """,
                filename=filename,
                total=total,
                batch_id=batch_id_var,
            )
            self.conn.commit()
            return batch_id_var.getvalue()[0]
        except oracledb.DatabaseError:
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def bulk_insert_accounts(self, rows: list, batch_id: int) -> int:
        cursor = self.conn.cursor()
        inserted = 0
        chunk_size = 500
        try:
            for start in range(0, len(rows), chunk_size):
                chunk = rows[start:start + chunk_size]

                client_data = [
                    {
                        "pan_check": r.pan_number, "pan_val": r.pan_number,
                        "name": r.full_name, "mobile": r.mobile, "email": r.email,
                    }
                    for r in chunk
                ]
                cursor.executemany(
                    """
                    MERGE INTO clients c
                    USING (SELECT :pan_check AS pan_number FROM dual) src
                    ON (c.pan_number = src.pan_number)
                    WHEN NOT MATCHED THEN
                        INSERT (pan_number, full_name, mobile, email)
                        VALUES (:pan_val, :name, :mobile, :email)
                    """,
                    client_data,
                )

                account_data = [
                    {"dp_id": r.dp_id, "pan": r.pan_number, "nominee": r.nominee_name}
                    for r in chunk
                ]
                cursor.executemany(
                    """
                    INSERT INTO demat_accounts (dp_id, client_id, nominee_name)
                    SELECT :dp_id, client_id, :nominee
                    FROM clients WHERE pan_number = :pan
                    """,
                    account_data,
                )
                inserted += len(chunk)
                self.conn.commit()

            return inserted
        except oracledb.DatabaseError:
            traceback.print_exc()
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def log_upload_errors(self, batch_id: int, invalid_rows: list):
        cursor = self.conn.cursor()
        try:
            data = [
                {"batch_id": batch_id, "row_num": row_num, "raw_val": raw, "msg": msg[:500]}
                for row_num, raw, msg in invalid_rows
            ]
            cursor.executemany(
                """
                INSERT INTO bulk_upload_errors (batch_id, row_number, raw_data, error_message)
                VALUES (:batch_id, :row_num, :raw_val, :msg)
                """,
                data,
            )
            self.conn.commit()
        finally:
            cursor.close()

    def finalize_batch(self, batch_id: int, success_count: int, error_count: int, status: str):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE bulk_upload_batches
                SET success_count = :success, error_count = :errors,
                    batch_status = :status, completed_at = SYSTIMESTAMP
                WHERE batch_id = :id
                """,
                success=success_count, errors=error_count, status=status, id=batch_id,
            )
            self.conn.commit()
        finally:
            cursor.close()


class AccountNotFoundError(Exception):
    pass

class InvalidStateError(Exception):
    pass
