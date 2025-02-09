import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar

class UgyeletiBeosztasGenerator:
    def __init__(self):
        self.orvosok = {}
        self.keresek = {}  # {év: {hónap: {orvos: {nap: státusz}}}}
        
    def excel_beolvasas(self, file):
        """Excel fájl beolvasása és feldolgozása"""
        try:
            # Excel fájl beolvasása, az összes munkalap
            xls = pd.ExcelFile(file)
            
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
                    df = pd.read_excel(file, sheet_name=sheet_name)
                    
                    # Az első oszlop általában "Unnamed: 0", ami az orvosok neveit tartalmazza
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
                            for nap in range(1, 32):  # maximum 31 nap lehet egy hónapban
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
            
            return True
            
        except Exception as e:
            st.error(f"Hiba az Excel beolvasása során: {str(e)}")
            return False
    
    def elerheto_orvosok(self, datum):
        """Visszaadja az adott napon elérhető orvosokat"""
        ev = datum.year
        honap = datum.month
        nap = datum.day
        
        elerheto = []
        for orvos in self.orvosok:
            # Ellenőrizzük, hogy van-e kérés az adott napra
            if (ev in self.keresek and 
                honap in self.keresek[ev] and 
                orvos in self.keresek[ev][honap] and 
                nap in self.keresek[ev][honap][orvos]):
                
                status = self.keresek[ev][honap][orvos][nap]
                if status not in ["Szabadság", "Ne ügyeljen"]:
                    elerheto.append(orvos)
            else:
                elerheto.append(orvos)
                
        return elerheto
    
    def beosztas_generalas(self, ev, honap):
        """Havi beosztás generálása"""
        napok_szama = calendar.monthrange(ev, honap)[1]
        beosztas = {}
        
        for nap in range(1, napok_szama + 1):
            datum = datetime(ev, honap, nap)
            elerheto_orvosok = self.elerheto_orvosok(datum)
            
            if not elerheto_orvosok:
                st.warning(f"Nem található elérhető orvos: {datum.strftime('%Y-%m-%d')}")
                continue
            
            # Válasszuk ki azt az orvost, akinek a legkevesebb ügyelete van
            valasztott_orvos = min(
                elerheto_orvosok,
                key=lambda x: self.orvosok[x]['ugyeletek_szama']
            )
            
            beosztas[datum.strftime('%Y-%m-%d')] = valasztott_orvos
            self.orvosok[valasztott_orvos]['ugyeletek_szama'] += 1
        
        return beosztas

def main():
    st.set_page_config(page_title="Ügyeleti Beosztás Generáló", layout="wide")
    st.title("Ügyeleti Beosztás Generáló")
    
    generator = UgyeletiBeosztasGenerator()
    
    # Excel feltöltés
    feltoltott_file = st.file_uploader("Ügyeleti kérések Excel feltöltése", type=["xlsx"])
    
    # Dátum választás
    col1, col2 = st.columns(2)
    with col1:
        ev = st.selectbox("Év", [2024, 2025])
    with col2:
        honap = st.selectbox("Hónap", range(1, 13))
    
    if feltoltott_file and st.button("Beosztás generálása"):
        try:
            # Excel beolvasása és feldolgozása
            if generator.excel_beolvasas(feltoltott_file):
                st.success("Excel fájl sikeresen beolvasva!")
                
                # Beosztás generálása
                beosztas = generator.beosztas_generalas(ev, honap)
                
                # Eredmények megjelenítése
                st.subheader("Generált beosztás")
                beosztas_df = pd.DataFrame(
                    [(datum, orvos) for datum, orvos in beosztas.items()],
                    columns=['Dátum', 'Orvos']
                )
                st.dataframe(beosztas_df)
                
                # Statisztika
                st.subheader("Ügyeletek statisztikája")
                statisztika_df = pd.DataFrame(
                    [(nev, adatok['ugyeletek_szama']) 
                     for nev, adatok in generator.orvosok.items()],
                    columns=['Orvos', 'Ügyeletek száma']
                )
                st.dataframe(statisztika_df)
                
                # Excel exportálás
                output = pd.ExcelWriter(f'ugyeleti_beosztas_{ev}_{honap}.xlsx', engine='openpyxl')
                beosztas_df.to_excel(output, sheet_name='Beosztás', index=False)
                statisztika_df.to_excel(output, sheet_name='Statisztika', index=False)
                output.close()
                
                with open(f'ugyeleti_beosztas_{ev}_{honap}.xlsx', 'rb') as f:
                    st.download_button(
                        label="Beosztás letöltése",
                        data=f,
                        file_name=f"ugyeleti_beosztas_{ev}_{honap}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        
        except Exception as e:
            st.error(f"Hiba történt: {str(e)}")
            st.error("Kérlek ellenőrizd az input fájl formátumát")

if __name__ == "__main__":
    main()