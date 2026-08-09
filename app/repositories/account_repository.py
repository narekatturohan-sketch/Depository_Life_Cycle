import oracledb
from app.models.schemas import AccountCreate


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
                "opened_date": row[5],
            }

        except oracledb.DatabaseError:
            self.conn.rollback()
            raise
        finally:
            cursor.close()