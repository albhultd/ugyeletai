import streamlit as st
import pandas as pd
from datetime import datetime
import calendar
import re
import io

class UgyeletiBeosztasGenerator:
    def __init__(self):
        self.orvosok = {}
        self.keresek = {}  # {év: {hónap: {orvos: {nap: státusz}}}}
        self.felhasznaloi_kivetelek = []  # [(orvos, datum, indok)]
        
    def excel_beolvasas(self, file_content):
        """Excel tartalom feldolgozása memóriából"""
        try:
            # Excel fájl beolvasása memóriából
            excel_buffer = io.BytesIO(file_content)
            xls = pd.ExcelFile(excel_buffer)
            
            # Munkalapok feldolgozása
            for sheet_name in xls.sheet_names:
                # Év és hónap meghatározása a munkalap nevéből
                if sheet_name.startswith('25 '):
                    ev = 2025
                    honap = sheet_name.split(' ')[1].lower()
                else:
                    ev = 2024
                    honap = sheet_name.lower()
                
                # Hónap sorszámának meghatározása
                honapok = {
                    'január': 1, 'február': 2, 'március': 3, 'április': 4,
                    'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
                    'szeptember': 9, 'október': 10, 'november': 11, 'december': 12
                }
                honap_szam = honapok.get(honap)
                
                if honap_szam:
                    # Munkalap beolvasása
                    df = pd.read_excel(excel_buffer, sheet_name=sheet_name)
                    
                    # Az első oszlop az orvosok neveit tartalmazza
                    orvos_oszlop = df.columns[0]
                    
                    # Orvosok és kéréseik feldolgozása
                    for index, row in df.iterrows():
                        orvos_nev = row[orvos_oszlop]
                        if pd.notna(orvos_nev) and isinstance(orvos_nev, str):
                            # Orvos hozzáadása a nyilvántartáshoz
                            if orvos_nev not in self.orvosok:
                                self.orvosok[orvos_nev] = {
                                    'nev': orvos_nev,
                                    'ugyeletek_szama': 0
                                }
                            
                            # Kérések feldolgozása
                            for nap in range(1, 32):
                                if str(nap) in df.columns:
                                    status = row[str(nap)]
                                    if pd.notna(status):
                                        if ev not in self.keresek:
                                            self.keresek[ev] = {}
                                        if honap_szam not in self.keresek[ev]:
                                            self.keresek[ev][honap_szam] = {}
                                        if orvos_nev not in self.keresek[ev][honap_szam]:
                                            self.keresek[ev][honap_szam][orvos_nev] = {}
                                        
                                        self.keresek[ev][honap_szam][orvos_nev][nap] = status
            
            # Excel buffer törlése
            excel_buffer.close()
            return True
            
        except Exception as e:
            st.error(f"Hiba az Excel beolvasása során: {str(e)}")
            return False

    # [A többi metódus változatlan marad...]

def main():
    st.set_page_config(page_title="Ügyeleti Beosztás Generáló", layout="wide")
    st.title("Ügyeleti Beosztás Generáló")
    
    # Session state inicializálása
    if 'generator' not in st.session_state:
        st.session_state.generator = UgyeletiBeosztasGenerator()
    
    # Excel feltöltés
    feltoltott_file = st.file_uploader("Ügyeleti kérések Excel feltöltése", type=["xlsx"])
    
    # Dátum választás
    col1, col2 = st.columns(2)
    with col1:
        ev = st.selectbox("Év", [2024, 2025])
    with col2:
        honap = st.selectbox("Hónap", range(1, 13))
    
    # Kivételek kezelése
    with st.expander("További kivételek megadása"):
        st.write("""
        Itt adhat meg további kivételeket szabad szöveggel. Például:
        - Dr. Kiss Péter 2024.01.15 szabadság
        - Nagy Katalin január 20 konferencia
        - Dr. Kovács 2024 február 5 továbbképzés
        """)
        kivetelek_szoveg = st.text_area(
            "Írja be a kivételeket", 
            help="Soronként egy kivétel. Írja be az orvos nevét, a dátumot és az indokot."
        )
    
    if feltoltott_file is not None and st.button("Beosztás generálása"):
        try:
            # Excel tartalom beolvasása
            file_content = feltoltott_file.read()
            
            # Excel feldolgozása
            if st.session_state.generator.excel_beolvasas(file_content):
                st.success("Excel adatok sikeresen beolvasva!")
                
                # Kivételek feldolgozása
                if kivetelek_szoveg:
                    st.session_state.generator.kivetel_hozzaadas(kivetelek_szoveg)
                
                # Beosztás generálása
                beosztas = st.session_state.generator.beosztas_generalas(ev, honap)
                
                # Eredmények megjelenítése
                st.subheader("Generált beosztás")
                beosztas_df = pd.DataFrame(
                    [(datum, orvos) for datum, orvos in beosztas.items()],
                    columns=['Dátum', 'Orvos']
                )
                beosztas_df = beosztas_df.sort_values('Dátum')
                st.dataframe(beosztas_df)
                
                # Kivételek megjelenítése
                if st.session_state.generator.felhasznaloi_kivetelek:
                    st.subheader("Feldolgozott kivételek")
                    kivetelek_df = pd.DataFrame(
                        st.session_state.generator.felhasznaloi_kivetelek,
                        columns=['Orvos', 'Dátum', 'Indok']
                    )
                    st.dataframe(kivetelek_df)
                
                # Statisztika
                st.subheader("Ügyeletek statisztikája")
                statisztika_df = pd.DataFrame(
                    [(nev, adatok['ugyeletek_szama']) 
                     for nev, adatok in st.session_state.generator.orvosok.items()],
                    columns=['Orvos', 'Ügyeletek száma']
                )
                st.dataframe(statisztika_df)
                
                # Excel exportálás memóriában
                output_buffer = io.BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    beosztas_df.to_excel(writer, sheet_name='Beosztás', index=False)
                    statisztika_df.to_excel(writer, sheet_name='Statisztika', index=False)
                    if st.session_state.generator.felhasznaloi_kivetelek:
                        kivetelek_df.to_excel(writer, sheet_name='Kivételek', index=False)
                
                output_buffer.seek(0)
                
                st.download_button(
                    label="Beosztás letöltése",
                    data=output_buffer,
                    file_name=f"ugyeleti_beosztas_{ev}_{honap}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Buffer törlése
                output_buffer.close()
        
        except Exception as e:
            st.error(f"Hiba történt: {str(e)}")
            st.error("Kérlek ellenőrizd az input fájl formátumát")

if __name__ == "__main__":
    main()