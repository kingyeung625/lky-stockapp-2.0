import streamlit as st
import pdfplumber
import pandas as pd
from io import BytesIO
import re

def extract_transactions(pdf_file):
    """
    Parses a PDF file to extract stock buy and sell transactions.
    This version uses a highly specific regular expression to find and
    parse transaction lines, making it robust against spacing issues.

    Args:
        pdf_file: A file-like object representing the PDF.

    Returns:
        A pandas DataFrame containing the extracted transactions,
        or None if no transactions are found.
    """
    transactions = []
    # This regex is designed to find a whole transaction line in one go.
    # It looks for: Action, Stock Name, Currency, and then four number groups.
    # It's much more reliable than splitting by spaces.
    pattern = re.compile(
        r"^(賣出平倉|買入開倉)\s+(.*?)\s+([A-Z]{3})\s+([\d,.]+\s+[\d,.]+)\s+(-?[\d,.]+)\s+(-?[\d,.]+)$"
    )

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and "交易-股票和股票期權" in text:
                    lines = text.split('\n')
                    for line in lines:
                        match = pattern.search(line.strip())
                        if match:
                            try:
                                action_chinese = match.group(1)
                                name_code = match.group(2)
                                currency = match.group(3)
                                qty_price_str = match.group(4)
                                amount_str = match.group(5)
                                change_str = match.group(6)

                                action = "Sell" if "賣出平倉" in action_chinese else "Buy"

                                # --- Parse the numbers ---
                                qty_price_parts = qty_price_str.split()
                                val1_str = qty_price_parts[0].replace(',', '')
                                val2_str = qty_price_parts[1].replace(',', '')

                                val1 = float(val1_str)
                                val2 = float(val2_str)

                                # The value with a decimal point is the price.
                                price = val1 if '.' in val1_str else val2
                                quantity = val2 if '.' in val1_str else val1

                                amount = float(amount_str.replace(',', ''))
                                change = float(change_str.replace(',', ''))

                                transactions.append({
                                    "Action": action,
                                    "Stock Name": name_code,
                                    "Quantity": int(quantity),
                                    "Price": price,
                                    "Amount": amount,
                                    "Currency": currency,
                                    "Net Change": change
                                })
                            except (ValueError, IndexError, TypeError):
                                # If parsing this specific line fails, skip it and try the next.
                                continue
        if transactions:
            return pd.DataFrame(transactions)
        else:
            return None

    except Exception as e:
        st.error(f"An error occurred while processing the PDF: {e}")
        return None

# --- Streamlit App UI ---

st.set_page_config(layout="wide", page_title="Transaction Extractor")

st.title("📈 PDF Statement Transaction Extractor")
st.markdown("""
Upload your daily statement PDF file to automatically extract all your buy and sell stock transactions.
The app will scan the document and display the trades in a clean table below.
""")

# --- Instructions and App Layout ---
with st.expander("How to use this app"):
    st.markdown("""
    1.  **Upload your PDF:** Click on the 'Browse files' button or drag and drop your PDF statement into the designated area.
    2.  **View Transactions:** The app will automatically process the file. If any stock trades are found, they will appear in the 'Extracted Transactions' table.
    3.  **No Data Stored:** Your uploaded file is processed in memory and is not saved or stored anywhere.
    """)

uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type="pdf",
    help="Please upload the PDF version of your daily statement."
)

if uploaded_file is not None:
    # To read the uploaded file, we need to wrap it in a BytesIO object
    # because pdfplumber expects a file path or a binary stream.
    bytes_data = uploaded_file.getvalue()
    pdf_stream = BytesIO(bytes_data)

    with st.spinner('Analyzing your statement...'):
        df_transactions = extract_transactions(pdf_stream)

    st.subheader("Extracted Transactions")
    if df_transactions is not None and not df_transactions.empty:
        st.dataframe(
            df_transactions,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Quantity": st.column_config.NumberColumn(format="%d"),
                "Price": st.column_config.NumberColumn(format="$%.4f"),
                "Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Net Change": st.column_config.NumberColumn(format="%.2f"),
            }
        )
    else:
        st.warning("No stock transactions could be found in the uploaded PDF. Please ensure the PDF contains a '交易-股票和股票期權' (Transactions - Stocks and Stock Options) section with valid trade entries.")

st.markdown("---")
st.markdown("Created with [Streamlit](https://streamlit.io).")

