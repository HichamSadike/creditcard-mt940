"""Transaction processor that coordinates CSV parsing and MT940 formatting."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from ..parsers.parser_factory import ParserFactory
from ..parsers.base_parser import BaseParser
from ..mt940.formatter import MT940Formatter, Transaction, AccountStatement
from ..camt.formatter import CAMT053Formatter


class TransactionProcessor:
    """Main processor for converting bank files to MT940."""
    
    def __init__(self):
        self.parser_factory = ParserFactory()
        self.mt940_formatter = MT940Formatter()
        self.camt053_formatter = CAMT053Formatter()
    
    def process_file_to_mt940(
        self,
        file_path: str,
        bank: str,
        account_number: Optional[str] = None,
        statement_number: Optional[str] = None,
        opening_balance: Optional[Decimal] = None
    ) -> str:
        """Process bank file and return MT940 formatted string."""
        
        # Get the appropriate parser for the bank
        parser = self.parser_factory.create_parser(bank)
        
        # Parse file
        transactions = parser.parse_file(file_path)
        
        # Get account info from file if not provided
        account_info = parser.get_account_info(file_path)
        
        # Use provided values or defaults
        final_account_number = account_number or account_info['account_number']
        final_statement_number = statement_number or self._generate_statement_number(account_info['start_date'])
        
        # Calculate opening balance if not provided
        if opening_balance is None:
            opening_balance = self._calculate_opening_balance(transactions)
        
        # Calculate closing balance
        closing_balance = self.mt940_formatter.calculate_closing_balance(opening_balance, transactions)
        
        # Create account statement
        statement = AccountStatement(
            account_number=final_account_number,
            statement_number=final_statement_number,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            transactions=transactions,
            currency="EUR",
            date=account_info['end_date']
        )
        
        # Format as MT940
        return self.mt940_formatter.format_statement(statement)
    
    def process_file_to_camt053(
        self,
        file_path: str,
        bank: str,
        account_number: Optional[str] = None,
        statement_number: Optional[str] = None,
        opening_balance: Optional[Decimal] = None
    ) -> str:
        """Process bank file and return CAMT.053 formatted XML string."""
        
        # Get the appropriate parser for the bank
        parser = self.parser_factory.create_parser(bank)
        
        # Parse file
        transactions = parser.parse_file(file_path)
        
        # Get account info from file if not provided
        account_info = parser.get_account_info(file_path)
        
        # Use provided values or defaults
        final_account_number = account_number or account_info['account_number']
        final_statement_number = statement_number or self._generate_statement_number(account_info['start_date'])
        
        # Calculate opening balance if not provided
        if opening_balance is None:
            opening_balance = self._calculate_opening_balance(transactions)
        
        # Calculate closing balance
        closing_balance = self.mt940_formatter.calculate_closing_balance(opening_balance, transactions)
        
        # Create account statement
        statement = AccountStatement(
            account_number=final_account_number,
            statement_number=final_statement_number,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            transactions=transactions,
            currency="EUR",
            date=account_info['end_date']
        )
        
        # Format as CAMT.053
        return self.camt053_formatter.format_statement(statement)
    
    def _generate_statement_number(self, start_date: datetime) -> str:
        """Generate statement number based on date."""
        return f"CC{start_date.strftime('%Y%m%d')}"
    
    def _calculate_opening_balance(self, transactions: List[Transaction]) -> Decimal:
        """Calculate opening balance - for credit card statements, typically 0."""
        # For credit card statements, we typically start with 0 balance
        # since we're only showing the transactions for the period
        return Decimal('0.00')
    
    def get_transaction_summary(self, file_path: str, bank: str) -> dict:
        """Get summary of transactions from bank file."""
        parser = self.parser_factory.create_parser(bank)
        transactions = parser.parse_file(file_path)
        account_info = parser.get_account_info(file_path)
        totals = parser.calculate_totals(transactions)
        
        return {
            'account_number': account_info['account_number'],
            'date_range': {
                'start': account_info['start_date'],
                'end': account_info['end_date']
            },
            'transaction_count': totals['transaction_count'],
            'total_credits': totals['total_credits'],
            'total_debits': totals['total_debits'],
            'net_total': totals['net_total'],
            'transactions': transactions
        }
    
    def validate_file_format(self, file_path: str, bank: str) -> dict:
        """Validate bank file format and return validation results."""
        parser = self.parser_factory.create_parser(bank)
        return parser.validate_file_format(file_path)
    
    def get_available_banks(self) -> dict:
        """Get information about all available banks."""
        return self.parser_factory.get_available_banks()
    
    def get_supported_file_types(self, bank: str) -> list:
        """Get supported file types for a specific bank."""
        return self.parser_factory.get_supported_file_types(bank)
    
    # Backward compatibility methods for existing code
    def process_csv_to_mt940(
        self,
        file_path: str,
        account_number: Optional[str] = None,
        statement_number: Optional[str] = None,
        opening_balance: Optional[Decimal] = None
    ) -> str:
        """Legacy method - uses original CSV parser for exact compatibility."""
        # Import the original CSV parser to ensure exact same behavior
        from ..parsers.csv_parser import CSVParser
        
        # Use original CSV parser directly
        csv_parser = CSVParser()
        transactions = csv_parser.parse_csv(file_path)
        
        # Get account info from CSV if not provided
        account_info = csv_parser.get_account_info(file_path)
        
        # Use provided values or defaults
        final_account_number = account_number or account_info['account_number']
        final_statement_number = statement_number or self._generate_statement_number(account_info['start_date'])
        
        # Calculate opening balance if not provided
        if opening_balance is None:
            opening_balance = self._calculate_opening_balance(transactions)
        
        # Calculate closing balance
        closing_balance = self.mt940_formatter.calculate_closing_balance(opening_balance, transactions)
        
        # Create account statement
        statement = AccountStatement(
            account_number=final_account_number,
            statement_number=final_statement_number,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            transactions=transactions,
            currency="EUR",
            date=account_info['end_date']
        )
        
        # Format as MT940
        return self.mt940_formatter.format_statement(statement)
    
    def process_csv_to_camt053(
        self,
        file_path: str,
        account_number: Optional[str] = None,
        statement_number: Optional[str] = None,
        opening_balance: Optional[Decimal] = None
    ) -> str:
        """Legacy method - defaults to Rabobank for backward compatibility."""
        return self.process_file_to_camt053(
            file_path, 'rabobank', account_number, statement_number, opening_balance
        )