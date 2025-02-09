import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import json

class ScheduleGenerator:
    def __init__(self):
        self.doctors = []
        self.constraints = {}
        
    def load_data(self, df):
        """Load and validate doctor data from DataFrame"""
        required_columns = {'Név', 'Elérhetőség', 'Max_ügyelet'}
        if not all(col in df.columns for col in required_columns):
            raise ValueError("Hiányzó kötelező oszlopok az Excel fájlból")
            
        self.doctors = df.to_dict('records')
        return True
        
    def add_constraint(self, doctor_name, date, constraint_type):
        """Add scheduling constraint for a specific doctor and date"""
        if doctor_name not in self.constraints:
            self.constraints[doctor_name] = {}
        self.constraints[doctor_name][date] = constraint_type
        
    def generate_schedule(self, year, month):
        """Generate monthly schedule considering all constraints"""
        num_days = calendar.monthrange(year, month)[1]
        schedule = {}
        doctor_counts = {doc['Név']: 0 for doc in self.doctors}
        
        for day in range(1, num_days + 1):
            date = datetime(year, month, day).strftime('%Y-%m-%d')
            available_doctors = self._get_available_doctors(date, doctor_counts)
            
            if not available_doctors:
                st.warning(f"Nem található elérhető orvos: {date}")
                continue
                
            # Select doctor with fewest assignments
            selected_doctor = min(available_doctors, key=lambda x: doctor_counts[x['Név']])
            schedule[date] = selected_doctor['Név']
            doctor_counts[selected_doctor['Név']] += 1
            
        return schedule, doctor_counts
    
    def _get_available_doctors(self, date, doctor_counts):
        """Get list of available doctors for a specific date"""
        available = []
        for doctor in self.doctors:
            if self._is_doctor_available(doctor, date, doctor_counts):
                available.append(doctor)
        return available
    
    def _is_doctor_available(self, doctor, date, doctor_counts):
        """Check if a doctor is available for a specific date"""
        # Check max shifts constraint
        if doctor_counts[doctor['Név']] >= doctor['Max_ügyelet']:
            return False
            
        # Check specific date constraints
        if doctor['Név'] in self.constraints and date in self.constraints[doctor['Név']]:
            return False
            
        # Check availability pattern (implement your specific logic here)
        return True

def main():
    st.set_page_config(page_title="Orvosi Ügyeleti Beosztás Generáló", layout="wide")
    st.title("Orvosi Ügyeleti Beosztás Generáló")
    
    scheduler = ScheduleGenerator()
    
    # File upload
    uploaded_file = st.file_uploader("Tölts fel egy Excel fájlt", type=["xlsx"])
    
    # Date selection
    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox("Év", range(datetime.now().year, datetime.now().year + 2))
    with col2:
        month = st.selectbox("Hónap", range(1, 13))
    
    # Constraint input
    with st.expander("Egyéni korlátozások hozzáadása"):
        constraint_text = st.text_area(
            "Add meg a korlátozásokat (pl.: 'Dr. Kiss 2024-01-15 szabadság')",
            help="Soronként egy korlátozás. Formátum: 'Név YYYY-MM-DD ok'"
        )
    
    if uploaded_file and st.button("Beosztás generálása"):
        try:
            # Load data
            df = pd.read_excel(uploaded_file)
            scheduler.load_data(df)
            
            # Process constraints
            if constraint_text:
                for line in constraint_text.split('\n'):
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            doctor_name = parts[0]
                            date = parts[1]
                            constraint_type = ' '.join(parts[2:]) if len(parts) > 2 else 'unavailable'
                            scheduler.add_constraint(doctor_name, date, constraint_type)
            
            # Generate schedule
            schedule, doctor_counts = scheduler.generate_schedule(year, month)
            
            # Display results
            st.subheader("Generált beosztás")
            schedule_df = pd.DataFrame(
                [(date, doctor) for date, doctor in schedule.items()],
                columns=['Dátum', 'Orvos']
            )
            st.dataframe(schedule_df)
            
            # Display statistics
            st.subheader("Statisztika")
            stats_df = pd.DataFrame(
                [(name, count) for name, count in doctor_counts.items()],
                columns=['Orvos', 'Ügyeletek száma']
            )
            st.dataframe(stats_df)
            
            # Export to Excel
            excel_buffer = pd.ExcelWriter('schedule.xlsx', engine='openpyxl')
            schedule_df.to_excel(excel_buffer, sheet_name='Beosztás', index=False)
            stats_df.to_excel(excel_buffer, sheet_name='Statisztika', index=False)
            excel_buffer.close()
            
            with open('schedule.xlsx', 'rb') as f:
                st.download_button(
                    label="Beosztás letöltése",
                    data=f,
                    file_name=f"ugyeleti_beosztas_{year}_{month}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
        except Exception as e:
            st.error(f"Hiba történt: {str(e)}")
            st.error("Kérlek ellenőrizd az input fájl formátumát és a megadott korlátozásokat")

if __name__ == "__main__":
    main()