# ==============================
# ✅ 1. IMPORTS
# ==============================
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import time
import datetime
import os
import json

# Firebase
import firebase_admin
from firebase_admin import credentials, storage


# ==============================
# ✅ 2. INIT FASTAPI
# ==============================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================
# 🔥 3. INIT FIREBASE
# ==============================
firebase_json = os.environ.get("FIREBASE_KEY")

if not firebase_json:
    raise ValueError("FIREBASE_KEY environment variable not set")

cred_dict = json.loads(firebase_json)
cred = credentials.Certificate(cred_dict)

firebase_admin.initialize_app(cred, {
    'storageBucket': 'uploadpdf-c94b4.appspot.com'
})


# ==============================
# ✅ HELPER FUNCTIONS
# ==============================
def convert_role(code):
    return {
        "1": "Primary",
        "2": "Secondary",
        "3": "Concomitant"
    }.get(str(code), code)


def convert_gender(code):
    return {
        "1": "Male",
        "2": "Female"
    }.get(str(code), "Unknown")


def convert_route_list(route_string):
    if not route_string:
        return "Unknown"

    route_map = {
        "001": "Oral",
        "002": "Intravenous",
        "003": "Intramuscular",
        "004": "Subcutaneous",
        "030": "Oral",
        "042": "Intramuscular",
        "048": "Subcutaneous",
        "058": "Subcutaneous",
        "065": "Subcutaneous"
    }

    codes = [c.strip() for c in str(route_string).split(",") if c.strip()]
    routes = [route_map.get(code, "Unknown") for code in codes]

    return ", ".join(set(routes))


def get_manufacturer(drug_name):
    drug_name = drug_name.lower()

    if any(x in drug_name for x in ["semaglutide", "ozempic", "wegovy", "rybelsus"]):
        return "Novo Nordisk"
    if "aspirin" in drug_name:
        return "Bayer"
    if "metformin" in drug_name:
        return "Various"

    return "Unknown"


# ==============================
# ✅ HOME ROUTE
# ==============================
@app.get("/")
def home():
    return {"status": "API working 🚀"}


# ==============================
# 🚀 MAIN DOWNLOAD API
# ==============================
@app.get("/download")
def download(drug: str, start_year: int, end_year: int):

    all_data = []

    # ==============================
    # 🔥 YEAR LOOP (IMPORTANT FIX)
    # ==============================
    for year in range(start_year, end_year + 1):

        start = f"{year}0101"
        end = f"{year}1231"

        skip = 0
        limit = 100

        while True:

            url = f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:{drug}+AND+receivedate:[{start}+TO+{end}]&limit={limit}&skip={skip}"

            try:
                response = requests.get(url, timeout=30)

                if response.status_code != 200:
                    break

                data = response.json().get("results", [])
                if not data:
                    break

            except:
                time.sleep(2)
                continue

            for report in data:
                try:
                    case_id = report.get("safetyreportid", "")
                    country = report.get("primarysourcecountry", "")

                    patient = report.get("patient", {})
                    age = patient.get("patientonsetage", "")
                    gender = convert_gender(patient.get("patientsex", ""))
                    weight = patient.get("patientweight", "")

                    drugs = patient.get("drug", [])

                    drug_names = []
                    brand_names = []
                    roles = []
                    routes = []
                    start_dates = []
                    end_dates = []

                    for d in drugs:
                        name = d.get("medicinalproduct", "")
                        brand = d.get("openfda", {}).get("brand_name", [])

                        drug_names.append(name)
                        roles.append(convert_role(d.get("drugcharacterization", "")))
                        routes.append(convert_route_list(d.get("drugadministrationroute", "")))
                        start_dates.append(str(d.get("drugstartdate", "")))
                        end_dates.append(str(d.get("drugenddate", "")))

                        if brand:
                            brand_names.extend(brand)

                    reactions = patient.get("reaction", [])
                    adr_list = ", ".join([r.get("reactionmeddrapt", "") for r in reactions])

                    all_data.append({
                        "Case ID": case_id,
                        "Age": age,
                        "Gender": gender,
                        "Weight": weight,
                        "Country": country,
                        "Drugs": ", ".join(drug_names),
                        "Brand Names": ", ".join(set(brand_names)) if brand_names else "Unknown",
                        "Manufacturer": get_manufacturer(drug),
                        "Drug Role": ", ".join(roles),
                        "Route": ", ".join(set(routes)),
                        "Start Date": ", ".join(start_dates),
                        "End Date": ", ".join(end_dates),
                        "ADR": adr_list
                    })

                except:
                    continue

            skip += limit
            time.sleep(1)

    # ==============================
    # ✅ DATAFRAME
    # ==============================
    df = pd.DataFrame(all_data)

    if df.empty:
        return {"message": "No data found"}

    df = df.drop_duplicates(subset=["Case ID"])

    # ==============================
    # 🔥 SAVE FILE
    # ==============================
    filename = f"{drug}_{start_year}_{end_year}.xlsx"
    df.to_excel(filename, index=False)

    # ==============================
    # 🔥 UPLOAD TO FIREBASE
    # ==============================
    bucket = storage.bucket()
    blob = bucket.blob(f"reports/{filename}")

    blob.upload_from_filename(filename)
    blob.make_public()

    return JSONResponse({
        "message": "File uploaded successfully 🚀",
        "total_records": len(df),
        "download_url": blob.public_url
    })