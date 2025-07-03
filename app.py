"""Streamlit application for Credit Card to MT940 converter."""

import streamlit as st
import pandas as pd
import io
from datetime import datetime
from decimal import Decimal

from src.creditcard_mt940.processors.transaction_processor import TransactionProcessor


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Credit Card to MT940 Converter",
        page_icon="💳",
        layout="wide"
    )
    
    st.title("💳 Credit Card to MT940 Converter")
    st.markdown("Convert your credit card transactions from CSV format to MT940 bank format.")
    
    # Initialize processor
    processor = TransactionProcessor()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Optional account number override
        account_number = st.text_input(
            "Account Number (optional)",
            help="Override the account number from CSV file"
        )
        
        # Optional statement number
        statement_number = st.text_input(
            "Statement Number (optional)",
            help="Custom statement number (auto-generated if empty)"
        )
        
        # Optional opening balance
        opening_balance_str = st.text_input(
            "Opening Balance (optional)",
            value="0.00",
            help="Starting balance for the statement"
        )
        
        opening_balance = None
        if opening_balance_str:
            try:
                opening_balance = Decimal(opening_balance_str.replace(',', '.'))
            except:
                st.error("Invalid opening balance format")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Credit Card CSV File",
        type=['csv'],
        help="Upload your credit card transaction CSV file"
    )
    
    if uploaded_file is not None:
        # Save uploaded file temporarily
        temp_file_path = f"temp_{uploaded_file.name}"
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            # Validate CSV format
            validation_result = processor.validate_csv_format(temp_file_path)
            
            if not validation_result['valid']:
                st.error(f"CSV Validation Error: {validation_result['error']}")
                st.info("Expected CSV format:")
                st.code("""
Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT...;;;
                """)
                return
            
            st.success(f"✅ {validation_result['message']}")
            
            # Show file preview
            with st.expander("📋 CSV File Preview"):
                df = pd.read_csv(temp_file_path, sep=';', encoding='utf-8')
                st.dataframe(df.head(10), use_container_width=True)
            
            # Get transaction summary
            summary = processor.get_transaction_summary(temp_file_path)
            
            # Display summary
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Transactions", summary['transaction_count'])
            
            with col2:
                st.metric("Total Credits", f"€{summary['total_credits']:.2f}")
            
            with col3:
                st.metric("Total Debits", f"€{summary['total_debits']:.2f}")
            
            with col4:
                st.metric("Net Total", f"€{summary['net_total']:.2f}")
            
            # Show date range
            st.info(f"📅 Date Range: {summary['date_range']['start'].strftime('%d-%m-%Y')} to {summary['date_range']['end'].strftime('%d-%m-%Y')}")
            
            # Show processed transactions
            with st.expander("🔄 Processed Transactions"):
                transaction_data = []
                for t in summary['transactions']:
                    transaction_data.append({
                        'Date': t.date.strftime('%d-%m-%Y'),
                        'Amount': f"€{t.amount:.2f}",
                        'Description': t.description,
                        'Counter Account': t.counter_account,
                        'Reference': t.reference
                    })
                
                if transaction_data:
                    st.dataframe(pd.DataFrame(transaction_data), use_container_width=True)
            
            # Convert to MT940
            st.header("🏦 MT940 Conversion")
            
            if st.button("Convert to MT940", type="primary"):
                try:
                    with st.spinner("Converting to MT940 format..."):
                        mt940_content = processor.process_csv_to_mt940(
                            temp_file_path,
                            account_number=account_number or None,
                            statement_number=statement_number or None,
                            opening_balance=opening_balance
                        )
                    
                    st.success("✅ Conversion completed successfully!")
                    
                    # Show MT940 preview
                    with st.expander("📄 MT940 Preview"):
                        st.code(mt940_content, language='text')
                    
                    # Download button
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"mt940_{timestamp}.txt"
                    
                    st.download_button(
                        label="📥 Download MT940 File",
                        data=mt940_content,
                        file_name=filename,
                        mime="text/plain",
                        type="primary"
                    )
                    
                except Exception as e:
                    st.error(f"Error during conversion: {str(e)}")
                    st.error("Please check your CSV file format and try again.")
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
        
        finally:
            # Clean up temporary file
            try:
                import os
                os.remove(temp_file_path)
            except:
                pass
    
    # Instructions
    with st.expander("📖 Instructions"):
        st.markdown("""
        ### How to use this converter:
        
        1. **Upload CSV File**: Select your credit card transaction CSV file
        2. **Configure Settings** (optional): Set account number, statement number, or opening balance
        3. **Review Summary**: Check the transaction summary and processed transactions
        4. **Convert**: Click "Convert to MT940" to generate the MT940 format
        5. **Download**: Download the generated MT940 file
        
        ### CSV Format Requirements:
        - Semicolon (;) separated values
        - Required columns: `Tegenrekening IBAN`, `Transactiereferentie`, `Datum`, `Bedrag`, `Omschrijving`
        - Date format: DD-MM-YYYY
        - Amount format: European format (comma as decimal separator)
        
        ### Business Rules Applied:
        - **Exchange Rate Surcharges**: Combined with main transaction amounts
        - **Previous Statement Settlements**: Converted to positive amounts
        - **Final Payment Memos**: Ignored (last row indicators)
        - **Columns F, G, H**: Ignored as requested
        """)


if __name__ == "__main__":
    main()