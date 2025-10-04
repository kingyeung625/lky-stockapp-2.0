import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

def extract_transactions(pdf_file):
    """
    Parses a PDF file to extract stock buy and sell transactions.

    Args:
        pdf_file: A file-like object representing the PDF.

    Returns:
        A pandas DataFrame containing the extracted transactions,
        or None if no transactions are found.
    """
    transactions = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, y_tolerance=2)
                # We check for a specific header to make sure we're on the right page.
                if text and "交易-股票和股票期權" in text:
                    lines = text.split('\n')
                    for line in lines:
                        # Transaction lines in this statement start with these specific keywords.
                        if "買入開倉" in line or "賣出平倉" in line:
                            # Clean the line: remove quotes and split by comma.
                            # The PDF extractor formats the table into comma-separated values.
                            cleaned_line = line.strip().replace('"', '')
                            parts = [p.strip() for p in cleaned_line.split(',')]
                            
                            # A valid transaction line should have at least 6 parts.
                            if len(parts) >= 6:
                                try:
                                    action_chinese = parts[0]
                                    if action_chinese not in ["買入開倉", "賣出平倉"]:
                                        continue
                                    
                                    action = "Sell" if action_chinese == "賣出平倉" else "Buy"
                                    name_code = parts[1]
                                    currency = parts[2]

                                    # The fourth part contains quantity and price, separated by a space.
                                    qty_price_parts = parts[3].split()
                                    if len(qty_price_parts) != 2:
                                        continue # Skip if the format is not as expected.

                                    val1_str, val2_str = qty_price_parts
                                    val1 = float(val1_str.replace(',', ''))
                                    val2 = float(val2_str.replace(',', ''))

                                    # The value containing a decimal point is the price.
                                    price = val1 if '.' in val1_str else val2
                                    quantity = val2 if '.' in val1_str else val1
                                    
                                    amount = float(parts[4].replace(',', ''))
                                    change = float(parts[5].replace(',', ''))

                                    transactions.append({
                                        "Action": action,
                                        "Stock Name": name_code,
                                        "Quantity": int(quantity),
                                        "Price": price,
                                        "Amount": amount,
                                        "Currency": currency,
                                        "Net Change": change
                                    })
                                except (ValueError, IndexError):
                                    # Catches errors from malformed numbers or unexpected structures.
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
        st.warning("No stock transactions could be found in the uploaded PDF. The tool currently only extracts stock and ETF trades.")

st.markdown("---")
st.markdown("Created with [Streamlit](https://streamlit.io).")

