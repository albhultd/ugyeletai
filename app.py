import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, timedelta
import re
from transformers import pipeline
from dateutil import parser
from typing import Dict, List, Set

# Oldal konfiguráció
st.set_page_config(page_title="Havi Orvosi Ügyeleti Beosztás Generáló", layout="wide")

# Konstansok
MAX_CONSECUTIVE_DAYS = 2  # Maximum egymást követő ügyeleti napok
MIN_REST_DAYS = 2  # Minimum pihenőnapok száma két ügyelet között
WEEKEND_WEIGHT = 1.5  # Hétvégi ügyelet súlyozása

class DateRange:
    def __init__(self, start_date: datetime, end_date: datetime):
        self.start_date = start_date
        self.end_date = end_date

    def contains(self, date: datetime) -> bool:
        return self.start_date <= date <= self.end_date

class DoctorScheduler:
    def __init__(self):
        self.doctors_data = {}
        self.exceptions = {}
        self.assignments = {}
        self.workload = {}

    def parse_date_range(self, date_str: str) -> DateRange:
        """Dátum intervallum feldolgozása különböző formátumokban"""
        try:
            # Különböző dátum formátumok kezelése
            if '-' in date_str:
                start_str, end_str = date_str.split('-')
                start_date = parser.parse(start_str.strip())
                end_date = parser.parse(end_str.strip())
                return DateRange(start_date, end_date)
            else:
                date = parser.parse(date_str.strip())
                return DateRange(date, date)
        except Exception as e:
            st.warning(f"Dátum feldolgozási hiba: {date_str} - {str(e)}")
            return None

    def parse_exceptions(self, exceptions_text: str):
        """Kivételek részletes feldolgozása"""
        patterns = {
            'holiday': r'(.*?)\s*szabadságon\s*(.*)',
            'weekend': r'(.*?)\s*nem dolgozhat hétvégén',
            'specific_days': r'(.*?)\s*nem dolgozhat\s*(hétfőn|kedden|szerdán|csütörtökön|pénteken)',
            'consecutive': r'(.*?)\s*maximum\s*(\d+)\s*egymást követő nap',
            'monthly_max': r'(.*?)\s*maximum\s*(\d+)\s*ügyelet\s*havonta',
            'preferred_days': r'(.*?)\s*preferált napok:\s*(.*)',
        }

        for line in exceptions_text.split('\n'):
            line = line.strip()
            if not line:
                continue

            for exception_type, pattern in patterns.items():
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    doctor_name = match.group(1).strip()
                    if doctor_name not in self.exceptions:
                        self.exceptions[doctor_name] = {}

                    if exception_type == 'holiday':
                        date_range = self.parse_date_range(match.group(2))
                        if date_range:
                            self.exceptions[doctor_name]['holidays'] = \
                                self.exceptions[doctor_name].get('holidays', []) + [date_range]
                    elif exception_type == 'weekend':
                        self.exceptions[doctor_name]['no_weekends'] = True
                    elif exception_type == 'specific_days':
                        self.exceptions[doctor_name]['excluded_days'] = \
                            self.exceptions[doctor_name].get('excluded_days', []) + [match.group(2)]
                    elif exception_type == 'consecutive':
                        self.exceptions[doctor_name]['max_consecutive'] = int(match.group(2))
                    elif exception_type == 'monthly_max':
                        self.exceptions[doctor_name]['monthly_max'] = int(match.group(2))
                    elif exception_type == 'preferred_days':
                        self.exceptions[doctor_name]['preferred_days'] = \
                            [day.strip() for day in match.group(2).split(',')]

    def calculate_doctor_score(self, doctor: str, date: datetime) -> float:
        """Orvos pontszámának kiszámítása egy adott napra"""
        score = 1.0
        
        # Munkaterhelés alapú súlyozás
        current_workload = self.workload.get(doctor, 0)
        score -= (current_workload * 0.1)  # Csökkentjük a pontszámot a jelenlegi terhelés alapján

        # Preferált napok bónusz
        if doctor in self.exceptions and 'preferred_days' in self.exceptions[doctor]:
            if date.strftime('%A').lower() in self.exceptions[doctor]['preferred_days']:
                score += 0.5

        # Hétvégi bónusz/levonás
        if date.weekday() >= 5:  # Hétvége
            if self.exceptions.get(doctor, {}).get('no_weekends', False):
                return -1  # Nem dolgozhat hétvégén
            score *= WEEKEND_WEIGHT

        return score

st.title("Orvosi Ügyeleti Beosztás Generáló")
st.write("Töltsd fel az orvosi adatokat tartalmazó Excel fájlt, és generálj beosztást az ügyeletekhez!")

# Hugging Face nyelvi modell betöltése
@st.cache_resource
def load_model():
    return pipeline("text-generation", model="distilbert-base-multilingual-cased")

generator = load_model()

# Fájl feltöltése
uploaded_file = st.file_uploader("Tölts fel egy Excel fájlt", type=["xlsx"])

if uploaded_file:
    try:
        # Excel beolvasása
        df = pd.read_excel(uploaded_file)
        st.write("Feltöltött adatok:")
        st.dataframe(df)

        # Előkészítés
        df["Elérhető napok"] = df["Elérhetőség"].apply(lambda x: x.split(","))
        df["Korlátozások"] = df["Korlátozások"].apply(lambda x: x.split(",") if pd.notna(x) else [])
        foglalt_napok = {}
        beosztas = []

        # Beosztás generálása
        for nap in range(1, 8):  # Példa: 7 napos beosztás
            nap_nev = f"Nap {nap}"
            for index, row in df.iterrows():
                if nap_nev in row["Elérhető napok"]:
                    korlatozott = any(
                        foglalt_napok.get(nap_nev) == szemely
                        for szemely in row["Korlátozások"]
                    )
                    if not korlatozott:
                        foglalt_napok[nap_nev] = row["Név"]
                        prompt = f"{row['Név']} ügyel {nap_nev}-n, mert "
                        indoklas = generator(prompt, max_length=50, num_return_sequences=1)[0]["generated_text"]
                        beosztas.append({
                            "Nap": nap_nev,
                            "Orvos": row["Név"],
                            "Indoklás": indoklas
                        })
                        break

        # Eredmény megjelenítése
        beosztas_df = pd.DataFrame(beosztas)
        st.write("Generált Ügyeleti Beosztás:")
        st.dataframe(beosztas_df)

        # Exportálás Excelbe
        @st.cache_data
        def convert_to_excel(data):
            return data.to_excel(index=False, engine="openpyxl")

        excel_data = convert_to_excel(beosztas_df)
        st.download_button(
            label="Beosztás letöltése Excelben",
            data=excel_data,
            file_name="ugyeleti_beosztas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Hiba történt a fájl feldolgozása során: {e}")
else:
    st.info("Tölts fel egy fájlt a kezdéshez.")
