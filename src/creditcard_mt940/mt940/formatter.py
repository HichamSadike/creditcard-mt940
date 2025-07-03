"""MT940 formatter for converting transactions to SWIFT MT940 format."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Transaction:
    """Represents a single transaction."""
    date: datetime
    amount: Decimal
    description: str
    counter_account: Optional[str] = None
    reference: Optional[str] = None
    transaction_type: str = "NMSC"  # Non-swift code


@dataclass
class AccountStatement:
    """Represents an account statement."""
    account_number: str
    statement_number: str
    opening_balance: Decimal
    closing_balance: Decimal
    transactions: List[Transaction]
    currency: str = "EUR"
    date: Optional[datetime] = None


class MT940Formatter:
    """Formats transactions into MT940 format."""
    
    def __init__(self):
        self.transaction_reference_counter = 1
    
    def format_statement(self, statement: AccountStatement) -> str:
        """Format an account statement into MT940 format."""
        lines = []
        
        # Transaction reference number (field 20)
        lines.append(f":20:{statement.statement_number}")
        
        # Account identification (field 25)
        lines.append(f":25:{statement.account_number}")
        
        # Statement/sequence number (field 28C)
        lines.append(f":28C:{statement.statement_number}")
        
        # Opening balance (field 60F)
        opening_balance_line = self._format_balance(
            "60F", 
            statement.opening_balance, 
            statement.currency,
            statement.date or datetime.now()
        )
        lines.append(opening_balance_line)
        
        # Transactions (field 61 and 86)
        for transaction in statement.transactions:
            # Transaction line (field 61)
            transaction_line = self._format_transaction(transaction)
            lines.append(transaction_line)
            
            # Transaction information (field 86)
            info_line = self._format_transaction_info(transaction)
            lines.append(info_line)
        
        # Closing balance (field 62F)
        closing_balance_line = self._format_balance(
            "62F", 
            statement.closing_balance, 
            statement.currency,
            statement.date or datetime.now()
        )
        lines.append(closing_balance_line)
        
        return "\n".join(lines)
    
    def _format_balance(self, field_code: str, amount: Decimal, currency: str, date: datetime) -> str:
        """Format a balance line."""
        credit_debit = "C" if amount >= 0 else "D"
        abs_amount = abs(amount)
        date_str = date.strftime("%y%m%d")
        
        # Format amount without decimal point
        amount_str = f"{abs_amount:.2f}".replace(".", "")
        
        return f":{field_code}:{credit_debit}{date_str}{currency}{amount_str}"
    
    def _format_transaction(self, transaction: Transaction) -> str:
        """Format a transaction line (field 61)."""
        date_str = transaction.date.strftime("%y%m%d")
        
        # Credit/debit indicator
        credit_debit = "C" if transaction.amount >= 0 else "D"
        
        # Format amount without decimal point
        amount_str = f"{abs(transaction.amount):.2f}".replace(".", "")
        
        # Transaction reference
        ref = f"{self.transaction_reference_counter:010d}"
        self.transaction_reference_counter += 1
        
        return f":61:{date_str}{credit_debit}{amount_str}{transaction.transaction_type}{ref}"
    
    def _format_transaction_info(self, transaction: Transaction) -> str:
        """Format transaction information line (field 86)."""
        info_parts = []
        
        # Add transaction description
        if transaction.description:
            info_parts.append(transaction.description[:35])  # Limit to 35 characters
        
        # Add counter account if available
        if transaction.counter_account:
            info_parts.append(f"IBAN:{transaction.counter_account}")
        
        # Add reference if available
        if transaction.reference:
            info_parts.append(f"REF:{transaction.reference}")
        
        return f":86:{' '.join(info_parts)}"
    
    def calculate_closing_balance(self, opening_balance: Decimal, transactions: List[Transaction]) -> Decimal:
        """Calculate closing balance from opening balance and transactions."""
        total_transactions = sum(t.amount for t in transactions)
        return opening_balance + total_transactions