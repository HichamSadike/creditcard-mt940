"""Tests for CSV parser."""

import pytest
import pandas as pd
from datetime import datetime
from decimal import Decimal
import tempfile
import os

from src.creditcard_mt940.parsers.csv_parser import CSVParser, RawTransaction


class TestCSVParser:
    """Test cases for CSVParser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = CSVParser()
        
        # Create sample CSV data
        self.sample_csv_data = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000008;1-3-2025;-19,3;GTRANSLATE.COM           GTRANSLATE.COUSAFL;19,99;USD;1,03575
NL54RABO0310737710;49000000009;1-3-2025;-0,39;Koersopslag;;;
NL54RABO0310737710;50000000005;26-3-2025;912,4;Verrekening vorig overzicht;;;
NL54RABO0310737710;50000000013;27-3-2025;-108;COOKIEBOT                KOEBENHAVN K DNK;;;
NL54RABO0310737710;53000000001;26-6-2025;-1642,63;Monthly Payment memo;;;"""
    
    def create_temp_csv(self, content):
        """Create a temporary CSV file with given content."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    def test_parse_raw_transactions(self):
        """Test parsing raw transactions from CSV."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            df = pd.read_csv(temp_file, sep=';', encoding='utf-8')
            raw_transactions = self.parser._parse_raw_transactions(df)
            
            # Should have 4 transactions (Monthly Payment memo is ignored)
            assert len(raw_transactions) == 4
            
            # Check first transaction
            first_transaction = raw_transactions[0]
            assert first_transaction.counter_account == "NL54RABO0310737710"
            assert first_transaction.reference == "49000000008"
            assert first_transaction.date == datetime(2025, 3, 1)
            assert first_transaction.amount == Decimal('-19.3')
            assert "GTRANSLATE.COM" in first_transaction.description
            assert first_transaction.original_amount == Decimal('19.99')
            assert first_transaction.original_currency == "USD"
            assert first_transaction.exchange_rate == Decimal('1.03575')
            
        finally:
            os.unlink(temp_file)
    
    def test_is_exchange_rate_surcharge(self):
        """Test identification of exchange rate surcharge transactions."""
        surcharge_transaction = RawTransaction(
            counter_account="NL54RABO0310737710",
            reference="49000000009",
            date=datetime(2025, 3, 1),
            amount=Decimal('-0.39'),
            description="Koersopslag"
        )
        
        normal_transaction = RawTransaction(
            counter_account="NL54RABO0310737710",
            reference="49000000008",
            date=datetime(2025, 3, 1),
            amount=Decimal('-19.3'),
            description="GTRANSLATE.COM"
        )
        
        assert self.parser._is_exchange_rate_surcharge(surcharge_transaction) is True
        assert self.parser._is_exchange_rate_surcharge(normal_transaction) is False
    
    def test_is_previous_statement_settlement(self):
        """Test identification of previous statement settlement transactions."""
        settlement_transaction = RawTransaction(
            counter_account="NL54RABO0310737710",
            reference="50000000005",
            date=datetime(2025, 3, 26),
            amount=Decimal('912.4'),
            description="Verrekening vorig overzicht"
        )
        
        normal_transaction = RawTransaction(
            counter_account="NL54RABO0310737710",
            reference="50000000013",
            date=datetime(2025, 3, 27),
            amount=Decimal('-108'),
            description="COOKIEBOT"
        )
        
        assert self.parser._is_previous_statement_settlement(settlement_transaction) is True
        assert self.parser._is_previous_statement_settlement(normal_transaction) is False
    
    def test_transactions_are_related(self):
        """Test identification of related transactions."""
        transaction1 = RawTransaction(
            counter_account="NL54RABO0310737710",
            reference="49000000008",
            date=datetime(2025, 3, 1),
            amount=Decimal('-19.3'),
            description="GTRANSLATE.COM"
        )
        
        transaction2 = RawTransaction(
            counter_account="NL54RABO0310737710",
            reference="49000000009",
            date=datetime(2025, 3, 1),
            amount=Decimal('-0.39'),
            description="Koersopslag"
        )
        
        unrelated_transaction = RawTransaction(
            counter_account="NL54RABO0310737710",
            reference="50000000013",
            date=datetime(2025, 3, 27),
            amount=Decimal('-108'),
            description="COOKIEBOT"
        )
        
        assert self.parser._transactions_are_related(transaction1, transaction2) is True
        assert self.parser._transactions_are_related(transaction1, unrelated_transaction) is False
    
    def test_apply_business_rules(self):
        """Test application of business rules."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            transactions = self.parser.parse_csv(temp_file)
            
            # Should have 3 processed transactions:
            # 1. GTRANSLATE.COM combined with Koersopslag
            # 2. Settlement (converted to positive)
            # 3. COOKIEBOT (standalone)
            assert len(transactions) == 3
            
            # Check combined transaction
            gtranslate_transaction = next(t for t in transactions if "GTRANSLATE.COM" in t.description)
            assert gtranslate_transaction.amount == Decimal('-19.69')  # -19.3 + -0.39
            assert "exchange rate surcharge" in gtranslate_transaction.description
            
            # Check settlement transaction
            settlement_transaction = next(t for t in transactions if "Settlement" in t.description)
            assert settlement_transaction.amount == Decimal('912.4')  # Positive
            
            # Check standalone transaction
            cookiebot_transaction = next(t for t in transactions if "COOKIEBOT" in t.description)
            assert cookiebot_transaction.amount == Decimal('-108')
            
        finally:
            os.unlink(temp_file)
    
    def test_get_account_info(self):
        """Test extraction of account information."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            account_info = self.parser.get_account_info(temp_file)
            
            assert account_info['account_number'] == "NL54RABO0310737710"
            assert account_info['start_date'] == datetime(2025, 3, 1)
            assert account_info['end_date'] == datetime(2025, 6, 26)
            
        finally:
            os.unlink(temp_file)
    
    def test_calculate_totals(self):
        """Test calculation of transaction totals."""
        temp_file = self.create_temp_csv(self.sample_csv_data)
        
        try:
            transactions = self.parser.parse_csv(temp_file)
            totals = self.parser.calculate_totals(transactions)
            
            assert totals['transaction_count'] == 3
            assert totals['total_credits'] == Decimal('912.4')
            assert totals['total_debits'] == Decimal('-127.69')  # -19.69 + -108
            assert totals['net_total'] == Decimal('784.71')  # 912.4 - 127.69
            
        finally:
            os.unlink(temp_file)
    
    def test_empty_csv(self):
        """Test handling of empty CSV files."""
        empty_csv = "Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers\n"
        temp_file = self.create_temp_csv(empty_csv)
        
        try:
            transactions = self.parser.parse_csv(temp_file)
            assert len(transactions) == 0
            
        finally:
            os.unlink(temp_file)
    
    def test_invalid_date_format(self):
        """Test handling of invalid date formats."""
        invalid_csv = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000008;invalid-date;-19,3;GTRANSLATE.COM;;;"""
        
        temp_file = self.create_temp_csv(invalid_csv)
        
        try:
            transactions = self.parser.parse_csv(temp_file)
            # Should skip invalid rows
            assert len(transactions) == 0
            
        finally:
            os.unlink(temp_file)
    
    def test_invalid_amount_format(self):
        """Test handling of invalid amount formats."""
        invalid_csv = """Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000008;1-3-2025;invalid-amount;GTRANSLATE.COM;;;"""
        
        temp_file = self.create_temp_csv(invalid_csv)
        
        try:
            transactions = self.parser.parse_csv(temp_file)
            # Should skip invalid rows
            assert len(transactions) == 0
            
        finally:
            os.unlink(temp_file)