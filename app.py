"""Streamlit application for Credit Card to MT940 converter with Numbr branding."""

import streamlit as st
import pandas as pd
from datetime import datetime
from decimal import Decimal

from src.creditcard_mt940.processors.transaction_processor import TransactionProcessor


def apply_numbr_styling():
    """Apply Numbr branding styles."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Red+Hat+Text:wght@400;500;600;700&display=swap');
    
    /* Main app styling */
    .main-header {
        display: flex;
        align-items: center;
        margin-bottom: 2rem;
        padding: 1rem 0;
        border-bottom: 2px solid #0b0c67;
    }
    
    .logo-container {
        margin-right: 2rem;
    }
    
    .logo {
        width: 80px;
        height: 80px;
        border-radius: 8px;
    }
    
    .title-container h1 {
        font-family: 'Red Hat Text', sans-serif !important;
        font-weight: 700 !important;
        color: #0b0c67 !important;
        margin: 0 !important;
        font-size: 2.5rem !important;
    }
    
    .subtitle {
        font-family: 'Red Hat Text', sans-serif !important;
        color: #666 !important;
        font-size: 1.1rem !important;
        margin-top: 0.5rem !important;
    }
    
    /* Override Streamlit's default fonts */
    .stApp {
        font-family: 'Red Hat Text', sans-serif !important;
    }
    
    /* Header styles */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Red Hat Text', sans-serif !important;
        font-weight: 600 !important;
        color: #0b0c67 !important;
    }
    
    /* Sidebar styling */
    .stSidebar {
        background-color: #f8f9fa !important;
        border-right: 2px solid #0b0c67 !important;
    }
    
    .stSidebar > div {
        padding-top: 2rem !important;
    }
    
    .stSidebar h2 {
        font-family: 'Red Hat Text', sans-serif !important;
        font-weight: 600 !important;
        color: #0b0c67 !important;
        border-bottom: 2px solid #0b0c67 !important;
        padding-bottom: 0.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    
    .stSidebar .stTextInput > div > div > input {
        border: 1px solid #0b0c67 !important;
        border-radius: 8px !important;
        font-family: 'Red Hat Text', sans-serif !important;
    }
    
    .stSidebar .stTextInput > div > div > input:focus {
        border-color: #0b0c67 !important;
        box-shadow: 0 0 0 2px rgba(11, 12, 103, 0.2) !important;
    }
    
    /* Button styling */
    .stButton > button {
        background-color: #0b0c67 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Red Hat Text', sans-serif !important;
        font-weight: 600 !important;
        padding: 0.75rem 2rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        background-color: #0a0b5a !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(11, 12, 103, 0.3) !important;
    }
    
    /* Download button styling */
    .stDownloadButton > button {
        background-color: #0b0c67 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Red Hat Text', sans-serif !important;
        font-weight: 600 !important;
    }
    
    /* File uploader styling */
    .stFileUploader > div > div {
        border: 2px dashed #0b0c67 !important;
        border-radius: 12px !important;
        background-color: #f8f9fa !important;
    }
    
    /* Metrics styling */
    .metric-container {
        background-color: white;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #e1e5e9;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    /* Success/info message styling */
    .stSuccess {
        background-color: #d4edda !important;
        border-color: #0b0c67 !important;
        color: #155724 !important;
        border-radius: 8px !important;
    }
    
    .stInfo {
        background-color: #e7f3ff !important;
        border-color: #0b0c67 !important;
        border-radius: 8px !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #f8f9fa !important;
        border-radius: 8px !important;
        font-family: 'Red Hat Text', sans-serif !important;
        font-weight: 600 !important;
        color: #0b0c67 !important;
    }
    
    /* Footer styling */
    .footer {
        margin-top: 3rem;
        padding: 2rem 0;
        border-top: 1px solid #e1e5e9;
        text-align: center;
        color: #666;
        font-family: 'Red Hat Text', sans-serif !important;
    }
    
    .footer a {
        color: #0b0c67 !important;
        text-decoration: none !important;
        font-weight: 600 !important;
    }
    
    .footer a:hover {
        text-decoration: underline !important;
    }
    </style>
    """, unsafe_allow_html=True)


def render_header():
    """Render the Numbr branded header."""
    st.markdown("""
    <div class="main-header">
        <div class="logo-container">
            <img src="https://numbr.nl/wp-content/uploads/Beeldmerk.jpg" class="logo" alt="Numbr Logo">
        </div>
        <div class="title-container">
            <h1>MT940 Converter</h1>
            <div class="subtitle">Convert credit card transactions to MT940 bank format</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_footer():
    """Render the footer with Numbr branding."""
    st.markdown("""
    <div class="footer">
        Powered by <a href="https://numbr.nl" target="_blank">Numbr</a> & Hicham- 
        Modern accounting solutions for entrepreneurs
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Numbr - MT940 Converter",
        page_icon="https://numbr.nl/wp-content/uploads/Beeldmerk.jpg",
        layout="wide"
    )
    
    # Apply Numbr styling
    apply_numbr_styling()
    
    # Render header
    render_header()
    
    # Initialize processor
    processor = TransactionProcessor()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Bank selection
        available_banks = processor.get_available_banks()
        bank_options = {info['display_name']: key for key, info in available_banks.items()}
        
        selected_bank_display = st.selectbox(
            "Select Bank",
            options=list(bank_options.keys()),
            help="Choose your bank to enable proper file processing"
        )
        selected_bank = bank_options[selected_bank_display]
        
        # Show supported file types for selected bank
        supported_types = processor.get_supported_file_types(selected_bank)
        st.info(f"**{selected_bank_display}** supports: {', '.join(supported_types).upper()} files")
        
        # Optional account number override
        account_number = st.text_input(
            "Account Number (optional)",
            help="Override the account number from file",
            placeholder="e.g., NL54RABO0310737710"
        )
        
        # Optional statement number
        statement_number = st.text_input(
            "Statement Number (optional)",
            help="Custom statement number (auto-generated if empty)",
            placeholder="e.g., CC20250701"
        )
        
        # Optional opening balance
        opening_balance_str = st.text_input(
            "Opening Balance (optional)",
            value="0.00",
            help="Starting balance for the statement",
            placeholder="0.00"
        )
        
        opening_balance = None
        if opening_balance_str:
            try:
                opening_balance = Decimal(opening_balance_str.replace(',', '.'))
            except:
                st.error("Invalid opening balance format")
    
    # File upload with dynamic file type support
    file_types = processor.get_supported_file_types(selected_bank)
    uploaded_file = st.file_uploader(
        f"Upload {selected_bank_display} Transaction File",
        type=file_types,
        help=f"Upload your {selected_bank_display} transaction file ({', '.join(file_types).upper()})"
    )
    
    if uploaded_file is not None:
        # Save uploaded file temporarily
        temp_file_path = f"temp_{uploaded_file.name}"
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        try:
            # Validate file format based on selected bank
            validation_result = processor.validate_file_format(temp_file_path, selected_bank)
            
            if not validation_result['valid']:
                st.error(f"File Validation Error: {validation_result['error']}")
                st.info(f"Expected {selected_bank_display} format:")
                
                # Show bank-specific format examples
                if selected_bank == 'rabobank':
                    st.code("""
Tegenrekening IBAN;Transactiereferentie;Datum;Bedrag;Omschrijving;Oorspr bedrag;Oorspr munt;Koers
NL54RABO0310737710;49000000007;27-2-2025;-108;COOKIEBOT...;;;
                    """)
                elif selected_bank == 'ing':
                    st.code("""
"Accountnummer","Kaartnummer","Naam op kaart","Transactiedatum","Boekingsdatum","Omschrijving","Valuta","Bedrag","Koers","Bedrag in EUR"
"00000374942","5534.****.****.5722","K.Z. CHIARETTI","2025-05-05","2025-05-05","Canva* 04506-56920230 Sydney AUS","","","","-11,99"
                    """)
                elif selected_bank == 'amex':
                    st.info("AMEX Excel files should contain transaction data with dates, amounts, and descriptions.")
                return
            
            st.success(f"✅ {validation_result['message']}")
            
            # Show file preview
            with st.expander(f"📋 {selected_bank_display} File Preview"):
                if selected_bank in ['rabobank']:
                    df = pd.read_csv(temp_file_path, sep=';', encoding='utf-8')
                    st.dataframe(df.head(10), use_container_width=True)
                elif selected_bank in ['ing']:
                    df = pd.read_csv(temp_file_path, sep=',', encoding='utf-8')
                    st.dataframe(df.head(10), use_container_width=True)
                elif selected_bank in ['amex']:
                    df = pd.read_excel(temp_file_path)
                    # Convert all columns to string to avoid Arrow serialization issues
                    df_display = df.head(10).astype(str)
                    st.dataframe(df_display, use_container_width=True)
            
            # Get transaction summary
            summary = processor.get_transaction_summary(temp_file_path, selected_bank)
            
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
                    with st.spinner(f"Converting {selected_bank_display} file to MT940 format..."):
                        # Use legacy method for Rabobank to ensure exact compatibility
                        if selected_bank == 'rabobank':
                            mt940_content = processor.process_csv_to_mt940(
                                temp_file_path,
                                account_number=account_number or None,
                                statement_number=statement_number or None,
                                opening_balance=opening_balance
                            )
                        else:
                            mt940_content = processor.process_file_to_mt940(
                                temp_file_path,
                                selected_bank,
                                account_number=account_number or None,
                                statement_number=statement_number or None,
                                opening_balance=opening_balance
                            )
                    
                    st.success("✅ MT940 conversion completed!")
                    
                    # Show MT940 preview
                    with st.expander("📄 MT940 Preview"):
                        st.code(mt940_content, language='text')
                    
                    # Download button - use original format for MoneyBird compatibility
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"mt940_{timestamp}.txt"  # Keep .txt extension as original
                    
                    st.download_button(
                        label="📥 Download MT940 File",
                        data=mt940_content,
                        file_name=filename,
                        mime="text/plain",
                        type="primary"
                    )
                    
                except Exception as e:
                    st.error(f"Error during MT940 conversion: {str(e)}")
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
        
        1. **Select Bank**: Choose your bank from the dropdown (Rabobank, ING, or AMEX)
        2. **Upload File**: Upload your transaction file (CSV/Excel depending on bank)
        3. **Configure Settings** (optional): Set account number, statement number, or opening balance
        4. **Review Summary**: Check the transaction summary and processed transactions
        5. **Convert**: Click "Convert to MT940" to generate the MT940 format
        6. **Download**: Download the generated MT940 file
        
        ### Supported Banks & Formats:
        
        #### **Rabobank**
        - File type: CSV (semicolon-separated)
        - Required columns: `Tegenrekening IBAN`, `Transactiereferentie`, `Datum`, `Bedrag`, `Omschrijving`
        - Date format: DD-MM-YYYY
        - Business rules: Exchange rate surcharges combined, settlements converted to positive
        
        #### **ING**
        - File type: CSV (comma-separated)
        - Required columns: `Accountnummer`, `Transactiedatum`, `Omschrijving`, `Bedrag in EUR`
        - Date format: YYYY-MM-DD
        - Business rules: Simple 1:1 transaction mapping, no merging
        
        #### **AMEX**
        - File type: Excel (.xlsx/.xls)
        - Required: Date, amount, and description columns
        - Business rules: Payments ("HARTELIJK BEDANKT VOOR UW BETALING") → positive, purchases → negative
        """)
    
    # Render footer
    render_footer()


if __name__ == "__main__":
    main()