import pdfplumber
import requests
import openai
import os
import json


from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from io import BytesIO
from dotenv import load_dotenv


load_dotenv()


app = FastAPI(title="Lender-PDF-Parse", openapi_tags=[])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_token(x_internal_token: str = Header(...)):
    internal_token = os.getenv("INTERNAL_TOKEN", default=None)
    if not internal_token:
        raise HTTPException(status_code=500, detail="Internal Token not found in environment variables")
    if not x_internal_token:
        raise HTTPException(status_code=401, detail="Provide the internal token")
    if x_internal_token != internal_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return x_internal_token


class ExtractTableRequest(BaseModel):
    pdf_url: str


# Function to extract tables from PDF content
def get_tables_from_pdf_content(pdf_content):
    tables = []
    with pdfplumber.open(BytesIO(pdf_content)) as pdf:
        for page in pdf.pages:
            extracted_tables = page.extract_tables()
            tables.extend(extracted_tables)
    return tables


# Function to query GPT-4 model
def query_gpt(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}],
    )
    return response.choices[0].message["content"].strip()


@app.post("/extracttable")
async def extract_table(req: ExtractTableRequest, token: str = Depends(verify_token)):
    try:
        # Fetch the PDF content from the URL
        response = requests.get(req.pdf_url)
        response.raise_for_status()  # Raise an exception for any HTTP errors

        # Get tables from the PDF content
        table_df = get_tables_from_pdf_content(response.content)

        openai_api_key = os.getenv("OPENAI_API_KEY", default=None)
        openai.api_key = openai_api_key

        # Format table data as JSON string
        table_json_str = json.dumps(table_df)

        # Prepare prompt for GPT-4 model
        prompt = f"""Given the following table data:
                 {table_json_str} Instructions: 1. Extract the rent roll table data. 2. Create an array named 
                 rentRollSummary. 3. Clean and format the extracted data to handle line breaks and other formatting 
                 issues appropriately. 4. For each row in the table: - Create a sub-array representing the row. - For 
                 each column in the row: - Create an object with three fields: key, value, and type. - Assign the key 
                 as the column header. - Assign the value as the corresponding cell value in the row. - Determine the 
                 type of the value (string, number, etc.). - Append the object to the sub-array. - Append the 
                 sub-array to the rentRollSummary array. 5. If there is a total annual revenue or any other total 
                 value given: - Create a new sub-array representing the totals row. - For each total value: - Create 
                 an object with three fields: key, value, and type. - Assign the key as the name of the total value (
                 e.g., Total Annual Revenue). - Assign the value as the total value. - Determine the type of the 
                 value (string, number, etc.). Also if there is field with $ sign then include with the $ sign and give the type of it as currency - Append the object to the sub-array. - Append the sub-array to the 
                 rentRollSummary array. 6. Generate a JSON response containing the rentRollSummary array with all the 
                 sub-arrays filled with objects representing row and total data. Note: Ensure to handle any line breaks and 
                     formatting issues in the extracted data to generate the JSON response accurately. Do not include 
                     any additional information or comments in the response. Ensure the output does not contain 
                     ellipsis (...) and provides the complete output. Do not include ellipsis in the output."""

        # Query GPT-4 model
        response = query_gpt(prompt)

        return json.loads(response)  # Return the JSON response

    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch PDF from URL: {e}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
