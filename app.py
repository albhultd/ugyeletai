import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import re
import io
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from functools import lru_cache

@dataclass
class Doctor:
    name: str
    shift_count: int = 0

class OptimizedScheduleGenerator:
    def __init__(self):
        self.doctors: Dict[str, Doctor] = {}
        self.requests: Dict[int, Dict[int, Dict[str, Dict[int, str]]]] = {}
        self.exceptions: List[Tuple[str, str, str]] = []
        
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats"""
        formats = [
            '%Y-%m-%d', '%Y.%m.%d', '%d-%m-%Y', '%d.%m.%Y',
            '%Y %B %d', '%Y %b %d', '%d %B %Y', '%d %b %Y'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def add_exception(self, text: str) -> None:
        """Process and add exceptions from user input"""
        if not text.strip():
            return
            
        for line in text.split('\n'):
            if not line.strip():
                continue
                
            try:
                # Split line into components
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                
                # Process doctor name
                name_end = 1
                if parts[0].startswith('Dr'):
                    name_end = 2
                doctor_name = ' '.join(parts[:name_end])
                
                # Find date in remaining parts
                date_str = None
                reason = []
                date_found = False
                
                for i, part in enumerate(parts[name_end:], name_end):
                    if not date_found:
                        # Try to parse as date
                        potential_date = self._parse_date(part)
                        if potential_date:
                            date_str = potential_date.strftime('%Y-%m-%d')
                            date_found = True
                            continue
                    
                    if date_found:
                        reason.append(part)
                
                if date_str and doctor_name:
                    self.exceptions.append((
                        doctor_name,
                        date_str,
                        ' '.join(reason) if reason else 'nem megadott'
                    ))
                
            except Exception as e:
                st.warning(f"Hiba a kivétel feldolgozása során: {line} - {str(e)}")

    @lru_cache(maxsize=128)
    def get_available_doctors(self, date: datetime) -> List[str]:
        """Get available doctors for a given date"""
        date_str = date.strftime('%Y-%m-%d')
        available = []
        
        for doctor_name, doctor in self.doctors.items():
            # Check user exceptions
            if any(exc[0] == doctor_name and exc[1] == date_str for exc in self.exceptions):
                continue
                
            # Check Excel requests
            year, month, day = date.year, date.month, date.day
            status = self.requests.get(year, {}).get(month, {}).get(doctor_name, {}).get(day)
            
            if not status or status not in ["Szabadság", "Ne ügyeljen"]:
                available.append(doctor_name)
                
        return available

    def process_excel(self, file_content: bytes) -> bool:
        """Process Excel file content"""
        try:
            excel_buffer = io.BytesIO(file_content)
            xls = pd.ExcelFile(excel_buffer)
            
            month_mapping = {
                'január': 1, 'február': 2, 'március': 3, 'április': 4,
                'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
                'szeptember': 9, 'október': 10, 'november': 11, 'december': 12
            }
            
            for sheet_name in xls.sheet_names:
                # Determine year and month from sheet name
                year = 2025 if sheet_name.startswith('25 ') else 2024
                month = sheet_name.split(' ')[1].lower() if year == 2025 else sheet_name.lower()
                month_num = month_mapping.get(month)
                
                if not month_num:
                    continue
                    
                # Read sheet data
                df = pd.read_excel(excel_buffer, sheet_name=sheet_name)
                doctor_column = df.columns[0]
                
                # Process doctors and their requests
                for _, row in df.iterrows():
                    doctor_name = row[doctor_column]
                    if pd.isna(doctor_name) or not isinstance(doctor_name, str):
                        continue
                        
                    # Add doctor if not exists
                    if doctor_name not in self.doctors:
                        self.doctors[doctor_name] = Doctor(name=doctor_name)
                        
                    # Process daily requests
                    for day in range(1, 32):
                        if str(day) not in df.columns:
                            continue
                            
                        status = row[str(day)]
                        if pd.isna(status):
                            continue
                            
                        # Add request to the structure
                        if year not in self.requests:
                            self.requests[year] = {}
                        if month_num not in self.requests[year]:
                            self.requests[year][month_num] = {}
                        if doctor_name not in self.requests[year][month_num]:
                            self.requests[year][month_num][doctor_name] = {}
                            
                        self.requests[year][month_num][doctor_name][day] = status
            
            return True
            
        except Exception as e:
            st.error(f"Excel feldolgozási hiba: {str(e)}")
            return False

    def generate_schedule(self, year: int, month: int) -> Dict[str, List[str]]:
        """Generate monthly schedule"""
        days_in_month = calendar.monthrange(year, month)[1]
        schedule = {}
        
        # Pre-calculate available doctors for the whole month
        availability_cache = {
            day: self.get_available_doctors(datetime(year, month, day))
            for day in range(1, days_in_month + 1)
        }
        
        # Sort days by number of available doctors (handle constrained days first)
        sorted_days = sorted(
            range(1, days_in_month + 1),
            key=lambda d: len(availability_cache[d])
        )
        
        for day in sorted_days:
            date = datetime(year, month, day)
            available_doctors = availability_cache[day]
            
            if len(available_doctors) < 2:
                st.warning(f"Nincs elegendő elérhető orvos {date.strftime('%Y-%m-%d')} napra!")
                continue
                
            # Select doctors with minimum shifts
            selected = sorted(
                available_doctors,
                key=lambda x: self.doctors[x].shift_count
            )[:2]
            
            schedule[date.strftime('%Y-%m-%d')] = selected
            
            # Update shift counts
            for doctor_name in selected:
                self.doctors[doctor_name].shift_count += 1
        
        return schedule

def main():
    st.set_page_config(
        page_title="Ügyeleti Beosztás Generáló",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("Ügyeleti Beosztás Generáló")
    
    # Initialize session state
    if 'generator' not in st.session_state:
        st.session_state.generator = OptimizedScheduleGenerator()
    
    # File upload
    uploaded_file = st.file_uploader(
        "Ügyeleti kérések Excel feltöltése",
        type=["xlsx"],
        help="Válassza ki az Excel fájlt az ügyeleti kérésekkel"
    )
    
    # Date selection
    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox("Év", [2024, 2025])
    with col2:
        month = st.selectbox(
            "Hónap",
            list(range(1, 13)),
            format_func=lambda x: calendar.month_name[x]
        )
    
    # Exceptions input
    with st.expander("További kivételek megadása"):
        st.write("""
        Itt adhat meg további kivételeket szabad szöveggel. Például:
        - Dr. Kiss Péter 2024.01.15 szabadság
        - Nagy Katalin január 20 konferencia
        - Dr. Kovács 2024 február 5 továbbképzés
        """)
        exceptions_text = st.text_area(
            "Írja be a kivételeket",
            help="Soronként egy kivétel. Írja be az orvos nevét, a dátumot és az indokot."
        )
    
    if uploaded_file is not None and st.button("Beosztás generálása", type="primary"):
        try:
            with st.spinner("Beosztás generálása folyamatban..."):
                # Process Excel file
                file_content = uploaded_file.read()
                if st.session_state.generator.process_excel(file_content):
                    st.success("Excel adatok sikeresen beolvasva!")
                    
                    # Process exceptions
                    if exceptions_text:
                        st.session_state.generator.add_exception(exceptions_text)
                    
                    # Generate schedule
                    schedule = st.session_state.generator.generate_schedule(year, month)
                    
                    # Display results
                    st.subheader("Generált beosztás")
                    schedule_df = pd.DataFrame(
                        [(date, ", ".join(doctors)) for date, doctors in schedule.items()],
                        columns=['Dátum', 'Orvosok']
                    )
                    schedule_df = schedule_df.sort_values('Dátum')
                    
                    # Display schedule
                    st.dataframe(
                        schedule_df,
                        height=400,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Display exceptions
                    if st.session_state.generator.exceptions:
                        st.subheader("Feldolgozott kivételek")
                        exceptions_df = pd.DataFrame(
                            list(set(st.session_state.generator.exceptions)),
                            columns=['Orvos', 'Dátum', 'Indok']
                        )
                        st.dataframe(
                            exceptions_df,
                            height=300,
                            use_container_width=True,
                            hide_index=True
                        )
                    
                    # Display statistics
                    st.subheader("Ügyeletek statisztikája")
                    stats_df = pd.DataFrame(
                        [(doc.name, doc.shift_count)
                         for doc in st.session_state.generator.doctors.values()],
                        columns=['Orvos', 'Ügyeletek száma']
                    )
                    st.dataframe(
                        stats_df,
                        height=200,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Export to Excel
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        schedule_df.to_excel(writer, sheet_name='Beosztás', index=False)
                        stats_df.to_excel(writer, sheet_name='Statisztika', index=False)
                        if st.session_state.generator.exceptions:
                            exceptions_df.to_excel(writer, sheet_name='Kivételek', index=False)
                    
                    output.seek(0)
                    st.download_button(
                        label="Beosztás letöltése Excel formátumban",
                        data=output,
                        file_name=f"ugyeleti_beosztas_{year}_{month}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
        except Exception as e:
            st.error(f"Hiba történt: {str(e)}")
            st.error("Kérjük ellenőrizze a bemeneti fájl formátumát")

if __name__ == "__main__":
    main()