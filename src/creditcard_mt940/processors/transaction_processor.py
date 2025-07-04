"""Transaction processor that coordinates CSV parsing and MT940 formatting."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from ..parsers.csv_parser import CSVParser
from ..mt940.formatter import MT940Formatter, Transaction, AccountStatement
from ..camt.formatter import CAMT053Formatter


class TransactionProcessor:
    """Main processor for converting CSV to MT940."""
    
    def __init__(self):
        self.csv_parser = CSVParser()
        self.mt940_formatter = MT940Formatter()
        self.camt053_formatter = CAMT053Formatter()
    
    def process_csv_to_mt940(
        self,
        file_path: str,
        account_number: Optional[str] = None,
        statement_number: Optional[str] = None,
        opening_balance: Optional[Decimal] = None
    ) -> str:
        """Process CSV file and return MT940 formatted string."""
        
        # Parse CSV file
        transactions = self.csv_parser.parse_csv(file_path)
        
        # Get account info from CSV if not provided
        account_info = self.csv_parser.get_account_info(file_path)
        
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
        """Process CSV file and return CAMT.053 formatted XML string."""
        
        # Parse CSV file
        transactions = self.csv_parser.parse_csv(file_path)
        
        # Get account info from CSV if not provided
        account_info = self.csv_parser.get_account_info(file_path)
        
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
    
    def get_transaction_summary(self, file_path: str) -> dict:
        """Get summary of transactions from CSV file."""
        transactions = self.csv_parser.parse_csv(file_path)
        account_info = self.csv_parser.get_account_info(file_path)
        totals = self.csv_parser.calculate_totals(transactions)
        
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
    
    def validate_csv_format(self, file_path: str) -> dict:
        """Validate CSV file format and return validation results."""
        try:
            import pandas as pd
            
            # Try to read the CSV
            df = pd.read_csv(file_path, sep=';', encoding='utf-8')
            
            # Check required columns
            required_columns = [
                'Tegenrekening IBAN',
                'Transactiereferentie', 
                'Datum',
                'Bedrag',
                'Omschrijving'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    'valid': False,
                    'error': f"Missing required columns: {', '.join(missing_columns)}",
                    'columns_found': list(df.columns)
                }
            
            # Check if we have any data
            if len(df) == 0:
                return {
                    'valid': False,
                    'error': "CSV file is empty",
                    'columns_found': list(df.columns)
                }
            
            # Try to parse a few transactions to check format
            validation_errors = []
            
            for index, row in df.head(5).iterrows():
                # Check date format
                try:
                    datetime.strptime(str(row['Datum']), '%d-%m-%Y')
                except ValueError:
                    validation_errors.append(f"Invalid date format in row {index}: {row['Datum']}")
                
                # Check amount format
                try:
                    Decimal(str(row['Bedrag']).replace(',', '.'))
                except:
                    validation_errors.append(f"Invalid amount format in row {index}: {row['Bedrag']}")
            
            if validation_errors:
                return {
                    'valid': False,
                    'error': "Format validation errors: " + "; ".join(validation_errors),
                    'columns_found': list(df.columns)
                }
            
            return {
                'valid': True,
                'message': f"CSV file is valid with {len(df)} transactions",
                'columns_found': list(df.columns),
                'row_count': len(df)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Error reading CSV file: {str(e)}",
                'columns_found': []
            }