import tempfile
import pandas as pd
import tabula
import os


from fastapi import FastAPI, File, UploadFile, Response
from io import BytesIO


app = FastAPI()


# Function to extract tables from a PDF file using tabula
def extract_tables_from_pdf(pdf_file_path):
    tables = tabula.read_pdf(pdf_file_path, pages='all')

    # Check if tables were extracted successfully
    if tables:
        table_data = []
        for table in tables:
            df = table
            table_data.append(df)
        return table_data
    else:
        return None


@app.post("/extract-tables/")
async def extract_tables(file: UploadFile = File(...)):
    # Read the uploaded PDF file from memory
    pdf_bytes = await file.read()
    BytesIO(pdf_bytes)

    # Save the PDF file to a temporary file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        tmp_file.write(pdf_bytes)
        tmp_file_path = tmp_file.name

    # Call the function to extract tables from the PDF file using tabula
    tables = extract_tables_from_pdf(tmp_file_path)

    # Remove the temporary file
    os.unlink(tmp_file_path)

    if tables:
        # Combine all tables into a single DataFrame
        combined_df = pd.concat(tables, ignore_index=True)

        # Convert the DataFrame to CSV format
        csv_data = combined_df.to_csv(index=False)

        # Set response headers for CSV download
        headers = {
            "Content-Disposition": "attachment; filename=tables.csv",
            "Content-Type": "text/csv",
        }

        return Response(content=csv_data, headers=headers)
    else:
        return {"message": "No tables found in the PDF."}
