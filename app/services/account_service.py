import oracledb
from app.models.schemas import AccountCreate, AccountResponse
from app.repositories.account_repository import AccountRepository
from app.models.schemas import (
    AccountCreate, AccountResponse, ModificationRequest, RequestResponse,
)
from app.repositories.account_repository import (
    AccountRepository, AccountNotFoundError, InvalidStateError,
)

class AccountService:
    def __init__(self, connection: oracledb.Connection):
        self.repository = AccountRepository(connection)

    def create_account(self, data: AccountCreate) -> AccountResponse:
        """
        Creates a client (if new) and a demat account in one transaction.
        Returns the created account details.
        """
        account_data = self.repository.create_account(data)
        return AccountResponse(**account_data)

    def submit_modification(self, account_id: int, data: ModificationRequest) -> RequestResponse:
        changes = data.changed_fields()
        if not changes:
            raise ValueError("No fields provided to modify")
        result = self.repository.submit_modification(account_id, changes)
        return RequestResponse(**result)

    def approve_modification(self, request_id: int) -> dict:
        return self.repository.approve_modification(request_id)

    def reject_modification(self, request_id: int, reason: str) -> dict:
        return self.repository.reject_modification(request_id, reason)