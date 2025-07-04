"""Tests for parser factory."""

import pytest
from src.creditcard_mt940.parsers.parser_factory import ParserFactory
from src.creditcard_mt940.parsers.rabobank_parser import RabobankParser
from src.creditcard_mt940.parsers.ing_parser import IngParser
from src.creditcard_mt940.parsers.amex_parser import AmexParser


class TestParserFactory:
    """Test cases for ParserFactory."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.factory = ParserFactory()
    
    def test_get_available_banks(self):
        """Test getting available banks."""
        banks = self.factory.get_available_banks()
        
        assert isinstance(banks, dict)
        assert 'rabobank' in banks
        assert 'ing' in banks
        assert 'amex' in banks
        
        # Check bank info structure
        rabobank_info = banks['rabobank']
        assert rabobank_info['name'] == 'Rabobank'
        assert rabobank_info['supported_files'] == ['csv']
        assert rabobank_info['display_name'] == 'Rabobank'
    
    def test_create_parser_rabobank(self):
        """Test creating Rabobank parser."""
        parser = self.factory.create_parser('rabobank')
        assert isinstance(parser, RabobankParser)
        assert parser.get_bank_name() == 'Rabobank'
        assert parser.get_supported_file_types() == ['csv']
    
    def test_create_parser_ing(self):
        """Test creating ING parser."""
        parser = self.factory.create_parser('ing')
        assert isinstance(parser, IngParser)
        assert parser.get_bank_name() == 'ING'
        assert parser.get_supported_file_types() == ['csv']
    
    def test_create_parser_amex(self):
        """Test creating AMEX parser."""
        parser = self.factory.create_parser('amex')
        assert isinstance(parser, AmexParser)
        assert parser.get_bank_name() == 'AMEX'
        assert parser.get_supported_file_types() == ['xlsx', 'xls']
    
    def test_create_parser_case_insensitive(self):
        """Test that parser creation is case insensitive."""
        parser1 = self.factory.create_parser('RABOBANK')
        parser2 = self.factory.create_parser('Rabobank')
        parser3 = self.factory.create_parser('rabobank')
        
        assert all(isinstance(p, RabobankParser) for p in [parser1, parser2, parser3])
    
    def test_create_parser_invalid_bank(self):
        """Test creating parser for invalid bank."""
        with pytest.raises(ValueError) as exc_info:
            self.factory.create_parser('invalid_bank')
        
        assert "Unknown bank 'invalid_bank'" in str(exc_info.value)
        assert "Available banks:" in str(exc_info.value)
    
    def test_get_supported_file_types(self):
        """Test getting supported file types for banks."""
        rabobank_types = self.factory.get_supported_file_types('rabobank')
        ing_types = self.factory.get_supported_file_types('ing')
        amex_types = self.factory.get_supported_file_types('amex')
        
        assert rabobank_types == ['csv']
        assert ing_types == ['csv']
        assert amex_types == ['xlsx', 'xls']
    
    def test_detect_bank_from_file_not_implemented(self):
        """Test that auto-detection is not implemented."""
        with pytest.raises(NotImplementedError):
            self.factory.detect_bank_from_file('test.csv')