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
    transaction_type: str = "TRANSFER"  # CARD, TRANSFER, DIRECT_DEBIT, CREDIT


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
        # Reset transaction counter for each statement to ensure consistent numbering
        self.transaction_reference_counter = 1
        lines = []
        
        # MT940 header
        lines.append(":940:")
        
        # Transaction reference number (field 20) - match working format
        ref_number = statement.statement_number.replace('CC', '940S')
        lines.append(f":20:{ref_number}")
        
        # Account identification (field 25) - include currency
        lines.append(f":25:{statement.account_number} {statement.currency}")
        
        # Statement/sequence number (field 28C) - use simplified format
        seq_number = statement.statement_number.replace('CC20', '').replace('25', '25')
        if len(seq_number) > 5:
            seq_number = seq_number[-5:]  # Take last 5 digits
        lines.append(f":28C:{seq_number}")
        
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
        
        # Available balance (field 64)
        available_balance_line = self._format_balance(
            "64", 
            statement.closing_balance, 
            statement.currency,
            statement.date or datetime.now()
        )
        lines.append(available_balance_line)
        
        # Forward available balance (field 65) - typically same as closing balance
        forward_balance_line = self._format_balance(
            "65", 
            statement.closing_balance, 
            statement.currency,
            statement.date or datetime.now()
        )
        lines.append(forward_balance_line)
        
        return "\n".join(lines)
    
    def _format_balance(self, field_code: str, amount: Decimal, currency: str, date: datetime) -> str:
        """Format a balance line."""
        credit_debit = "C" if amount >= 0 else "D"
        abs_amount = abs(amount)
        date_str = date.strftime("%y%m%d")
        
        # Format amount with comma as decimal separator and proper padding
        amount_str = f"{abs_amount:.2f}".replace(".", ",")
        # Pad with zeros to ensure minimum 12 characters for amount
        amount_parts = amount_str.split(",")
        amount_str = f"{amount_parts[0]:>09},{amount_parts[1]:0<2}"
        
        return f":{field_code}:{credit_debit}{date_str}{currency}{amount_str}"
    
    def _format_transaction(self, transaction: Transaction) -> str:
        """Format a transaction line (field 61)."""
        date_str = transaction.date.strftime("%y%m%d")
        
        # Credit/debit indicator
        credit_debit = "C" if transaction.amount >= 0 else "D"
        
        # Format amount with comma as decimal separator and proper padding
        amount_str = f"{abs(transaction.amount):.2f}".replace(".", ",")
        # Pad with zeros to ensure minimum 12 characters for amount
        amount_parts = amount_str.split(",")
        amount_str = f"{amount_parts[0]:>09},{amount_parts[1]:0<2}"
        
        # Transaction code based on transaction type - match working format
        transaction_code = self._get_transaction_code(transaction)
        
        # Transaction reference in working format: NONREF//reference_number
        if transaction.reference:
            ref_number = transaction.reference
        else:
            ref_number = f"{self.transaction_reference_counter:011d}"
            self.transaction_reference_counter += 1
        
        # Add counter account on next line - always use 0000000000 like working format
        line1 = f":61:{date_str}{credit_debit}{amount_str}{transaction_code}NONREF//{ref_number}"
        return f"{line1}\n0000000000"
    
    def _get_transaction_code(self, transaction: Transaction) -> str:
        """Get appropriate SWIFT transaction code based on transaction type."""
        # Map transaction types to SWIFT codes
        if transaction.transaction_type == "CARD":
            return "N002"  # Card transactions
        elif transaction.transaction_type == "TRANSFER":
            return "N544"  # Bank transfers
        elif transaction.transaction_type == "DIRECT_DEBIT":
            return "N064"  # Direct debits
        elif transaction.transaction_type == "CREDIT":
            return "N541"  # Credits
        else:
            return "N544"  # Default to transfer
    
    def _format_transaction_info(self, transaction: Transaction) -> str:
        """Format transaction information line (field 86) to match working format."""
        # Working format: /TRCD/002/BENM//NAME/COOKIEBOT KOEBENHAVN/REMI/description
        
        # Get transaction code for TRCD field
        trcd_code = "002" if transaction.transaction_type == "CARD" else "544"
        
        # Extract merchant name and location from description
        description = transaction.description.upper()
        
        # Split description into name and additional info
        if len(description) > 25:
            name_part = description[:25]
            remi_part = description[25:] if len(description) > 25 else ""
        else:
            name_part = description
            remi_part = ""
        
        # Build the /TRCD/ format string like working example
        info_line = f"/TRCD/{trcd_code}/BENM//NAME/{name_part}"
        
        if remi_part:
            info_line += f"/REMI/{remi_part}"
        
        return f":86:{info_line}"
    
    def calculate_closing_balance(self, opening_balance: Decimal, transactions: List[Transaction]) -> Decimal:
        """Calculate closing balance from opening balance and transactions."""
        total_transactions = sum(t.amount for t in transactions)
        return opening_balance + total_transactions