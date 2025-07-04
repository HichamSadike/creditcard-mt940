"""Tests for CAMT.053 formatter."""

import pytest
from datetime import datetime
from decimal import Decimal
import xml.etree.ElementTree as ET

from src.creditcard_mt940.camt.formatter import CAMT053Formatter
from src.creditcard_mt940.mt940.formatter import Transaction, AccountStatement


class TestCAMT053Formatter:
    """Test cases for CAMT053Formatter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = CAMT053Formatter()
        
        # Sample transactions
        self.sample_transactions = [
            Transaction(
                date=datetime(2025, 3, 1),
                amount=Decimal('-19.69'),
                description="GTRANSLATE.COM (incl. exchange rate surcharge)",
                counter_account="NL54RABO0310737710",
                reference="49000000008",
                transaction_type="TRANSFER"
            ),
            Transaction(
                date=datetime(2025, 3, 26),
                amount=Decimal('912.40'),
                description="Settlement previous statement",
                counter_account="NL54RABO0310737710",
                reference="50000000005",
                transaction_type="CREDIT"
            )
        ]
    
    def test_format_statement(self):
        """Test complete CAMT.053 statement formatting."""
        statement = AccountStatement(
            account_number="NL54RABO0310737710",
            statement_number="CC20250301",
            opening_balance=Decimal('0.00'),
            closing_balance=Decimal('892.71'),
            transactions=self.sample_transactions,
            currency="EUR",
            date=datetime(2025, 3, 31)
        )
        
        # Format statement
        camt053_content = self.formatter.format_statement(statement)
        
        # Check it's valid XML
        root = ET.fromstring(camt053_content)
        
        # Check root element
        assert root.tag.endswith('Document')
        
        # Check namespace
        assert 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.02' in root.tag
        
        # Check required elements exist
        assert camt053_content.count('<MsgId>') == 1
        assert camt053_content.count('<IBAN>') >= 1
        assert camt053_content.count('<Amt') >= 1
        assert camt053_content.count('<Ntry>') == 2  # Two transactions
        
        # Check account number
        assert "NL54RABO0310737710" in camt053_content
        
        # Check statement number
        assert "CC20250301" in camt053_content
        
        # Check transaction descriptions
        assert "GTRANSLATE.COM" in camt053_content
        assert "Settlement previous statement" in camt053_content
    
    def test_transaction_types(self):
        """Test different transaction type mappings."""
        transactions = [
            Transaction(
                date=datetime(2025, 3, 1),
                amount=Decimal('-10.00'),
                description="Card payment",
                transaction_type="CARD"
            ),
            Transaction(
                date=datetime(2025, 3, 2),
                amount=Decimal('-20.00'),
                description="Direct debit",
                transaction_type="DIRECT_DEBIT"
            ),
            Transaction(
                date=datetime(2025, 3, 3),
                amount=Decimal('30.00'),
                description="Credit transfer",
                transaction_type="CREDIT"
            )
        ]
        
        statement = AccountStatement(
            account_number="NL54RABO0310737710",
            statement_number="TEST001",
            opening_balance=Decimal('0.00'),
            closing_balance=Decimal('0.00'),
            transactions=transactions,
            currency="EUR",
            date=datetime(2025, 3, 31)
        )
        
        camt053_content = self.formatter.format_statement(statement)
        
        # Check transaction type codes are mapped correctly
        assert "CCRD" in camt053_content  # Card
        assert "DDBT" in camt053_content  # Direct debit
        assert "TRAF" in camt053_content  # Transfer (default for CREDIT)
    
    def test_balance_indicators(self):
        """Test credit/debit indicators."""
        positive_statement = AccountStatement(
            account_number="NL54RABO0310737710",
            statement_number="TEST001",
            opening_balance=Decimal('0.00'),
            closing_balance=Decimal('100.00'),
            transactions=[],
            currency="EUR"
        )
        
        negative_statement = AccountStatement(
            account_number="NL54RABO0310737710",
            statement_number="TEST002",
            opening_balance=Decimal('0.00'),
            closing_balance=Decimal('-50.00'),
            transactions=[],
            currency="EUR"
        )
        
        pos_content = self.formatter.format_statement(positive_statement)
        neg_content = self.formatter.format_statement(negative_statement)
        
        # Check balance indicators
        assert "<CdtDbtInd>CRDT</CdtDbtInd>" in pos_content
        assert "<CdtDbtInd>DBIT</CdtDbtInd>" in neg_content
    
    def test_xml_structure(self):
        """Test basic XML structure compliance."""
        statement = AccountStatement(
            account_number="NL54RABO0310737710",
            statement_number="TEST001",
            opening_balance=Decimal('0.00'),
            closing_balance=Decimal('0.00'),
            transactions=self.sample_transactions,
            currency="EUR"
        )
        
        camt053_content = self.formatter.format_statement(statement)
        
        # Parse XML to ensure it's well-formed
        root = ET.fromstring(camt053_content)
        
        # Check required CAMT.053 structure
        assert root.find('.//{urn:iso:std:iso:20022:tech:xsd:camt.053.001.02}BkToCstmrStmt') is not None
        assert root.find('.//{urn:iso:std:iso:20022:tech:xsd:camt.053.001.02}GrpHdr') is not None
        assert root.find('.//{urn:iso:std:iso:20022:tech:xsd:camt.053.001.02}Stmt') is not None