import oracledb
from app.models.schemas import AccountCreate, AccountResponse
from app.repositories.account_repository import AccountRepository

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