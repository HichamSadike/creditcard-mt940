"""Parser factory for selecting the appropriate bank parser."""

from typing import Dict, Type
from .base_parser import BaseParser
from .rabobank_parser import RabobankParser
from .ing_parser import IngParser
from .amex_parser import AmexParser


class ParserFactory:
    """Factory class for creating bank-specific parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, Type[BaseParser]] = {
            'rabobank': RabobankParser,
            'ing': IngParser,
            'amex': AmexParser
        }
    
    def get_available_banks(self) -> Dict[str, Dict]:
        """Get information about all available banks and their supported formats."""
        banks = {}
        for bank_key, parser_class in self._parsers.items():
            parser = parser_class()
            banks[bank_key] = {
                'name': parser.get_bank_name(),
                'supported_files': parser.get_supported_file_types(),
                'display_name': parser.get_bank_name()
            }
        return banks
    
    def create_parser(self, bank: str) -> BaseParser:
        """Create a parser instance for the specified bank."""
        bank_lower = bank.lower()
        if bank_lower not in self._parsers:
            available_banks = list(self._parsers.keys())
            raise ValueError(f"Unknown bank '{bank}'. Available banks: {available_banks}")
        
        parser_class = self._parsers[bank_lower]
        return parser_class()
    
    def get_supported_file_types(self, bank: str) -> list:
        """Get supported file types for a specific bank."""
        parser = self.create_parser(bank)
        return parser.get_supported_file_types()
    
    def detect_bank_from_file(self, file_path: str) -> str:
        """Try to automatically detect the bank from the file format (optional feature)."""
        # This could be implemented to auto-detect based on file structure
        # For now, we require explicit bank selection
        raise NotImplementedError("Auto-detection not implemented - please select bank manually")