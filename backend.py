# ==============================
# ✅ 1. IMPORTS
# ==============================
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import time
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

def convert_gender(code):
    return {
        "1": "Male",
        "2": "Female"
    }.get(str(code), "Unknown")


def convert_role(code):
    return {
        "1": "Primary Suspect",
        "2": "Secondary Suspect",
        "3": "Concomitant"
    }.get(str(code), "Unknown")


def convert_route(code):
    return {
        "001": "Oral",
        "002": "Intravenous",
        "003": "Intramuscular",
        "004": "Subcutaneous",
        "058": "Subcutaneous"
    }.get(str(code), "Unknown")


def parse_dose(d):
    """
    Combine structured dose fields safely
    """
    num = d.get("drugstructuredosagenumb", "")
    unit = d.get("drugstructuredosageunit", "")

    unit_map = {
        "001": "mg",
        "002": "g",
        "003": "ml"
    }

    unit_text = unit_map.get(str(unit), "")

    if num:
        return f"{num} {unit_text}".strip()

    return "Unknown"


def get_seriousness(report):
    return {
        "Serious": "Yes" if report.get("serious") == "1" else "No",
        "Death": "Yes" if report.get("seriousnessdeath") == "1" else "No",
        "Hospitalization": "Yes" if report.get("seriousnesshospitalization") == "1" else "No",
        "Life Threatening": "Yes" if report.get("seriousnesslifethreatening") == "1" else "No"
    }


def reporter_qualification(code):
    return {
        "1": "Physician",
        "2": "Pharmacist",
        "3": "Other HCP",
        "4": "Lawyer",
        "5": "Consumer"
    }.get(str(code), "Unknown")


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

                    # 🔥 Seriousness
                    seriousness = get_seriousness(report)

                    # 🔥 Reporter
                    reporter = report.get("primarysource", {})
                    qualification = reporter_qualification(
                        reporter.get("qualification", "")
                    )

                    patient = report.get("patient", {})
                    age = patient.get("patientonsetage", "")
                    gender = convert_gender(patient.get("patientsex", ""))
                    weight = patient.get("patientweight", "")

                    drugs = patient.get("drug", [])

                    primary_drug = ""
                    secondary_drugs = []
                    concomitant_drugs = []
                    dose = ""
                    indication = ""
                    route = ""

                    for d in drugs:
                        role = convert_role(d.get("drugcharacterization", ""))

                        if role == "Primary Suspect":
                            primary_drug = d.get("medicinalproduct", "")
                            dose = parse_dose(d)
                            indication = d.get("drugindication", "")
                            route = convert_route(d.get("drugadministrationroute", ""))

                        elif role == "Secondary Suspect":
                            secondary_drugs.append(d.get("medicinalproduct", ""))

                        elif role == "Concomitant":
                            concomitant_drugs.append(d.get("medicinalproduct", ""))

                    reactions = patient.get("reaction", [])
                    adr_list = ", ".join(
                        [r.get("reactionmeddrapt", "") for r in reactions]
                    )

                    all_data.append({
                        "Case ID": case_id,
                        "Country": country,
                        "Age": age,
                        "Gender": gender,
                        "Weight": weight,

                        # 🔴 Seriousness
                        "Serious": seriousness["Serious"],
                        "Death": seriousness["Death"],
                        "Hospitalization": seriousness["Hospitalization"],
                        "Life Threatening": seriousness["Life Threatening"],

                        # 💊 Drug Info
                        "Primary Drug": primary_drug,
                        "Secondary Drugs": ", ".join(secondary_drugs),
                        "Concomitant Drugs": ", ".join(concomitant_drugs),
                        "Dose": dose,
                        "Route": route,
                        "Indication": indication,

                        # 👨‍⚕️ Reporter
                        "Reporter Qualification": qualification,

                        # ⚠️ ADR
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