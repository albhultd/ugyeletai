import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import re
import io
from typing import Dict, List, Tuple, Optional

class OnCallScheduleGenerator:
    def __init__(self):
        self.doctors: Dict[str, Dict] = {}
        self.requests: Dict[int, Dict] = {}  # {year: {month: {doctor: {day: status}}}}
        self.user_exceptions: List[Tuple[str, str, str]] = []  # [(doctor, date, reason)]
        
    def read_excel(self, file_content: bytes) -> bool:
        """Process Excel content from memory"""
        try:
            excel_buffer = io.BytesIO(file_content)
            xls = pd.ExcelFile(excel_buffer)
            
            months_map = {
                'január': 1, 'február': 2, 'március': 3, 'április': 4,
                'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
                'szeptember': 9, 'október': 10, 'november': 11, 'december': 12
            }
            
            for sheet_name in xls.sheet_names:
                # Determine year and month from sheet name
                year = 2025 if sheet_name.startswith('25 ') else 2024
                month_str = sheet_name.split(' ')[1].lower() if sheet_name.startswith('25 ') else sheet_name.lower()
                month_num = months_map.get(month_str)
                
                if month_num:
                    self._process_sheet(excel_buffer, sheet_name, year, month_num)
            
            excel_buffer.close()
            return True
            
        except Exception as e:
            st.error(f"Hiba az Excel beolvasása során: {str(e)}")
            return False

    def _process_sheet(self, excel_buffer: io.BytesIO, sheet_name: str, year: int, month: int) -> None:
        """Process individual Excel sheet"""
        df = pd.read_excel(excel_buffer, sheet_name=sheet_name)
        doctor_column = df.columns[0]
        
        for _, row in df.iterrows():
            doctor_name = row[doctor_column]
            if pd.notna(doctor_name) and isinstance(doctor_name, str):
                # Add doctor if not exists
                if doctor_name not in self.doctors:
                    self.doctors[doctor_name] = {
                        'name': doctor_name,
                        'on_call_count': 0
                    }
                
                # Process requests for each day
                for day in range(1, 32):
                    if str(day) in df.columns:
                        status = row[str(day)]
                        if pd.notna(status):
                            self.requests.setdefault(year, {}).setdefault(month, {}).setdefault(doctor_name, {})[day] = status

    def add_exception(self, text: str) -> None:
        """Process exceptions from user text"""
        if not text:
            return
            
        for line in text.split('\n'):
            if not line.strip():
                continue
                
            try:
                # Split text
                words = line.strip().split()
                if len(words) < 2:
                    continue
                
                # Process name
                name_end = 1
                if words[0].startswith('Dr'):
                    name_end = 2
                doctor_name = ' '.join(words[:name_end])
                
                # Process date
                date_start = None
                date_end = None
                date_index = name_end
                
                # Search for date range
                range_match = None
                for i, word in enumerate(words[date_index:], date_index):
                    if "között" in word or "-" in word:
                        range_text = ' '.join(words[date_index:i+2])
                        patterns = [
                            r'(\d{1,2})[.-](\d{1,2})',  # "22-28" format
                            r'(\d{1,2})\s*(?:és|-)?\s*(\d{1,2})\s+között',  # "22 és 28 között" format
                            r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})\s*(?:és|-)?\s*(\d{4})[.-](\d{1,2})[.-](\d{1,2})'  # full date range
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, range_text)
                            if match:
                                range_match = match
                                date_index = i
                                break
                        if range_match:
                            break
                
                # If range found
                if range_match:
                    months_map = {
                        'január': 1, 'február': 2, 'március': 3, 'április': 4,
                        'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
                        'szeptember': 9, 'október': 10, 'november': 11, 'december': 12,
                        'jan': 1, 'feb': 2, 'már': 3, 'ápr': 4, 'máj': 5, 'jún': 6,
                        'júl': 7, 'aug': 8, 'szept': 9, 'okt': 10, 'nov': 11, 'dec': 12
                    }
                    
                    # Find month and year
                    month = None
                    year = datetime.now().year
                    for word in words[:date_index]:
                        if word.lower() in months_map:
                            month = months_map[word.lower()]
                        elif word.isdigit() and len(word) == 4:
                            year = int(word)
                    
                    if month is None:
                        raise ValueError("Nem található hónap megjelölés")
                    
                    # Process range
                    if len(range_match.groups()) == 2:
                        day_start = int(range_match.group(1))
                        day_end = int(range_match.group(2))
                        date_start = datetime(year, month, day_start)
                        date_end = datetime(year, month, day_end)
                    elif len(range_match.groups()) == 6:
                        date_start = datetime(
                            int(range_match.group(1)),
                            int(range_match.group(2)),
                            int(range_match.group(3))
                        )
                        date_end = datetime(
                            int(range_match.group(4)),
                            int(range_match.group(5)),
                            int(range_match.group(6))
                        )
                
                # If no range, look for simple date
                else:
                    date_start = self._parse_simple_date(words[date_index:])
                    if date_start:
                        date_end = date_start
                
                if not date_start or not date_end:
                    st.warning(f"Nem sikerült feldolgozni a dátumot ebben a sorban: {line}")
                    continue
                
                # Process reason
                reason_words = []
                for word in words[date_index+1:]:
                    if not any(k in word.lower() for k in ['között', 'és']):
                        reason_words.append(word)
                reason = ' '.join(reason_words) if reason_words else 'nem elérhető'
                
                # Add exceptions for each day in range
                current_date = date_start
                while current_date <= date_end:
                    self.user_exceptions.append((
                        doctor_name,
                        current_date.strftime('%Y-%m-%d'),
                        reason
                    ))
                    current_date += timedelta(days=1)
                
            except Exception as e:
                st.warning(f"Hiba a sor feldolgozása során: {line} - {str(e)}")
                continue

    def _parse_simple_date(self, words: List[str]) -> Optional[datetime]:
        """Parse simple date format"""
        months_map = {
            'január': 1, 'február': 2, 'március': 3, 'április': 4,
            'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
            'szeptember': 9, 'október': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'már': 3, 'ápr': 4, 'máj': 5, 'jún': 6,
            'júl': 7, 'aug': 8, 'szept': 9, 'okt': 10, 'nov': 11, 'dec': 12
        }
        
        try:
            for i, word in enumerate(words):
                # YYYY-MM-DD or YYYY.MM.DD format
                try:
                    date_str = word.replace('.', '-')
                    return datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    pass
                
                # DD-MM-YYYY or DD.MM.YYYY format
                try:
                    date_str = word.replace('.', '-')
                    return datetime.strptime(date_str, '%d-%m-%Y')
                except ValueError:
                    pass
                
                # Hungarian month name format
                if i + 2 < len(words):
                    try:
                        year = int(words[i])
                        month = months_map.get(words[i + 1].lower())
                        day = int(words[i + 2])
                        if month:
                            return datetime(year, month, day)
                    except (ValueError, KeyError, IndexError):
                        pass
        except Exception:
            return None
        
        return None

    def get_available_doctors(self, date: datetime) -> List[str]:
        """Return available doctors for a given date"""
        year, month, day = date.year, date.month, date.day
        date_str = date.strftime('%Y-%m-%d')
        
        available = []
        for doctor in self.doctors:
            # Check user exceptions
            if any(exc[0] == doctor and exc[1] == date_str for exc in self.user_exceptions):
                continue
            
            # Check Excel requests
            status = self.requests.get(year, {}).get(month, {}).get(doctor, {}).get(day)
            if not status or status not in ["Szabadság", "Ne ügyeljen"]:
                available.append(doctor)
                
        return available
    
    def generate_schedule(self, year: int, month: int) -> Dict[str, str]:
        """Generate monthly schedule"""
        days_in_month = calendar.monthrange(year, month)[1]
        schedule = {}
        
        for day in range(1, days_in_month + 1):
            date = datetime(year, month, day)
            available_doctors = self.get_available_doctors(date)
            
            if not available_doctors:
                st.warning(f"Nem található elérhető orvos: {date.strftime('%Y-%m-%d')}")
                continue
            
            # Select doctor with least on-call shifts
            selected_doctor = min(
                available_doctors,
                key=lambda x: self.doctors[x]['on_call_count']
            )
            
            schedule[date.strftime('%Y-%m-%d')] = selected_doctor
            self.doctors[selected_doctor]['on_call_count'] += 1
        
        return schedule

def main():
    st.set_page_config(page_title="Ügyeleti Beosztás Generáló", layout="wide")
    st.title("Ügyeleti Beosztás Generáló")
    
    # Initialize session state
    if 'generator' not in st.session_state:
        st.session_state.generator = OnCallScheduleGenerator()
    
    # Excel upload
    uploaded_file = st.file_uploader("Ügyeleti kérések Excel feltöltése", type=["xlsx"])
    
    # Date selection
    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox("Év", [2024, 2025])
    with col2:
        month = st.selectbox("Hónap", range(1, 13))
    
    # Exception handling
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
    
    if uploaded_file is not None and st.button("Beosztás generálása"):
        try:
            # Read Excel content
            file_content = uploaded_file.read()
            
            # Process Excel
            if st.session_state.generator.read_excel(file_content):
                st.success("Excel adatok sikeresen beolvasva!")
                
                # Process exceptions
                if exceptions_text:
                    st.session_state.generator.add_exception(exceptions_text)
                
                # Generate schedule
                schedule = st.session_state.generator.generate_schedule(year, month)
                
                # Display results
                st.subheader("Generált beosztás")
                schedule_df = pd.DataFrame(
                    [(date, doctor) for date, doctor in schedule.items()],
                    columns=['Dátum', 'Orvos']
                )
                schedule_df = schedule_df.sort_values('Dátum')
                st.dataframe(schedule_df)
                
                # Display exceptions
                if st.session_state.generator.user_exceptions:
                    st.subheader("Feldolgozott kivételek")
                    exceptions_df = pd.DataFrame(
                        st.session_state.generator.user_exceptions,
                        columns=['Orvos', 'Dátum', 'Indok']
                    )
                    st.dataframe(exceptions_df)
                
                # Statistics
                st.subheader("Ügyeletek statisztikája")
                stats_df = pd.DataFrame(
                    [(name, data['on_call_count']) 
                     for name, data in st.session_state.generator.doctors.items()],
                    columns=['Orvos', 'Ügyeletek száma']
                )
                st.dataframe(stats_df)
                
                # Excel export in memory
                output_buffer = io.BytesIO()
                try:
                    with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                        schedule_df.to_excel(writer, sheet_name='Beosztás', index=False)
                        stats_df.to_excel(writer, sheet_name='Statisztika', index=False)
                        if st.session_state.generator.user_exceptions:
                            exceptions_df.to_excel(writer, sheet_name='Kivételek', index=False)
                    
                    output_buffer.seek(0)
                    st.download_button(
                        label="Beosztás letöltése",
                        data=output_buffer,
                        file_name=f"ugyeleti_beosztas_{year}_{month}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Hiba történt az Excel exportálása során: {str(e)}")
                finally:
                    output_buffer.close()
                    
        except Exception as e:
            st.error(f"Hiba történt: {str(e)}")
            st.error("Kérlek ellenőrizd az input fájl formátumát")

if __name__ == "__main__":
    main()