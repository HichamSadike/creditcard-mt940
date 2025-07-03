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
        assert "1969" in transaction_line  # Amount (19.69 without decimal)
        assert "NMSC" in transaction_line  # Transaction type
    
    def test_format_transaction_info(self):
        """Test formatting of transaction information."""
        transaction = self.sample_transactions[0]
        
        # Format transaction info
        info_line = self.formatter._format_transaction_info(transaction)
        
        # Check format
        assert info_line.startswith(":86:")
        assert "GTRANSLATE.COM" in info_line
        assert "IBAN:NL54RABO0310737710" in info_line
        assert "REF:49000000008" in info_line
    
    def test_format_balance(self):
        """Test balance formatting."""
        balance_line = self.formatter._format_balance(
            "60F",
            Decimal('100.50'),
            "EUR",
            datetime(2025, 3, 1)
        )
        
        # Check format
        assert balance_line == ":60F:C250301EUR10050"
    
    def test_format_balance_negative(self):
        """Test negative balance formatting."""
        balance_line = self.formatter._format_balance(
            "62F",
            Decimal('-50.25'),
            "EUR",
            datetime(2025, 3, 31)
        )
        
        # Check format
        assert balance_line == ":62F:D250331EUR5025"
    
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
        assert ":20:CC20250301" in mt940_content
        assert ":25:NL54RABO0310737710" in mt940_content
        assert ":28C:CC20250301" in mt940_content
        assert ":60F:C250331EUR0" in mt940_content
        assert ":62F:C250331EUR78471" in mt940_content
        
        # Check transactions are included
        assert ":61:" in mt940_content
        assert ":86:" in mt940_content
        assert "GTRANSLATE.COM" in mt940_content
        assert "Settlement previous statement" in mt940_content
        assert "COOKIEBOT" in mt940_content
    
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
        
        # Extract reference numbers (last 10 digits)
        ref1 = line1[-10:]
        ref2 = line2[-10:]
        
        assert ref1 != ref2
        assert int(ref2) == int(ref1) + 1