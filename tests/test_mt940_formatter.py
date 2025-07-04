"""Tests for MT940 formatter."""

import pytest
from datetime import datetime
from decimal import Decimal

from src.creditcard_mt940.mt940.formatter import MT940Formatter, Transaction, AccountStatement


class TestMT940Formatter:
    """Test cases for MT940Formatter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = MT940Formatter()
        
        # Sample transactions
        self.sample_transactions = [
            Transaction(
                date=datetime(2025, 3, 1),
                amount=Decimal('-19.69'),
                description="GTRANSLATE.COM (incl. exchange rate surcharge)",
                counter_account="NL54RABO0310737710",
                reference="49000000008"
            ),
            Transaction(
                date=datetime(2025, 3, 26),
                amount=Decimal('912.40'),
                description="Settlement previous statement",
                counter_account="NL54RABO0310737710",
                reference="50000000005"
            ),
            Transaction(
                date=datetime(2025, 3, 27),
                amount=Decimal('-108.00'),
                description="COOKIEBOT KOEBENHAVN K DNK",
                counter_account="NL54RABO0310737710",
                reference="50000000013"
            )
        ]
    
    def test_format_transaction(self):
        """Test formatting of individual transactions."""
        transaction = self.sample_transactions[0]
        
        # Format transaction
        transaction_line = self.formatter._format_transaction(transaction)
        
        # Check format
        assert transaction_line.startswith(":61:")
        assert "250301" in transaction_line  # Date
        assert "D" in transaction_line  # Debit indicator
        assert "000000019,69" in transaction_line  # Amount with comma and padding
        assert "N544" in transaction_line  # Transaction type (TRANSFER is default)
    
    def test_format_transaction_info(self):
        """Test formatting of transaction information."""
        transaction = self.sample_transactions[0]
        
        # Format transaction info
        info_line = self.formatter._format_transaction_info(transaction)
        
        # Check format
        assert info_line.startswith(":86:")
        assert "GTRANSLATE.COM" in info_line
        assert "/TRCD/" in info_line
        assert "/BENM//" in info_line
        assert "/NAME/" in info_line
    
    def test_format_balance(self):
        """Test balance formatting."""
        balance_line = self.formatter._format_balance(
            "60F",
            Decimal('100.50'),
            "EUR",
            datetime(2025, 3, 1)
        )
        
        # Check format
        assert balance_line == ":60F:C250301EUR000000100,50"
    
    def test_format_balance_negative(self):
        """Test negative balance formatting."""
        balance_line = self.formatter._format_balance(
            "62F",
            Decimal('-50.25'),
            "EUR",
            datetime(2025, 3, 31)
        )
        
        # Check format
        assert balance_line == ":62F:D250331EUR000000050,25"
    
    def test_calculate_closing_balance(self):
        """Test closing balance calculation."""
        opening_balance = Decimal('0.00')
        closing_balance = self.formatter.calculate_closing_balance(
            opening_balance,
            self.sample_transactions
        )
        
        expected = Decimal('-19.69') + Decimal('912.40') + Decimal('-108.00')
        assert closing_balance == expected
    
    def test_format_statement(self):
        """Test complete statement formatting."""
        statement = AccountStatement(
            account_number="NL54RABO0310737710",
            statement_number="CC20250301",
            opening_balance=Decimal('0.00'),
            closing_balance=Decimal('784.71'),
            transactions=self.sample_transactions,
            currency="EUR",
            date=datetime(2025, 3, 31)
        )
        
        # Format statement
        mt940_content = self.formatter.format_statement(statement)
        
        # Check required fields
        assert ":940:" in mt940_content  # MT940 header
        assert ":20:940S20250301" in mt940_content  # Updated format
        assert ":25:NL54RABO0310737710 EUR" in mt940_content  # Account with currency
        assert ":28C:50301" in mt940_content  # Simplified sequence number
        assert ":60F:C250331EUR000000000,00" in mt940_content  # Opening balance with comma
        assert ":62F:C250331EUR000000784,71" in mt940_content  # Closing balance with comma
        
        # Check transactions are included
        assert ":61:" in mt940_content
        assert ":86:" in mt940_content
        assert "GTRANSLATE.COM" in mt940_content
        assert "SETTLEMENT PREVIOUS STATE" in mt940_content  # Truncated in new format
        assert "COOKIEBOT" in mt940_content
        assert "NONREF//" in mt940_content  # New reference format
        assert "/TRCD/" in mt940_content  # New transaction info format
    
    def test_transaction_reference_counter(self):
        """Test that transaction reference counter increments."""
        transaction1 = Transaction(
            date=datetime(2025, 3, 1),
            amount=Decimal('-10.00'),
            description="Test 1"
        )
        
        transaction2 = Transaction(
            date=datetime(2025, 3, 2),
            amount=Decimal('-20.00'),
            description="Test 2"
        )
        
        # Format both transactions
        line1 = self.formatter._format_transaction(transaction1)
        line2 = self.formatter._format_transaction(transaction2)
        
        # Check that reference numbers are different
        assert line1 != line2
        
        # Extract reference numbers from the transaction lines
        # Reference is in format N544XXXXXXXXXX where X is the reference
        assert "0000000001" in line1
        assert "0000000002" in line2