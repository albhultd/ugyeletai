import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar

class UgyeletiBeosztasGenerator:
    def __init__(self):
        self.orvosok = {}
        self.kivetelek = {}
        self.maximum_ugyeletek = {}
        
    def excel_beolvasas(self, df):
        """Excel adatok beolvasása és feldolgozása"""
        try:
            # Az oszlopnevek a feltöltött Excel alapján lesznek frissítve
            for _, row in df.iterrows():
                nev = row['Név']  # Ez az oszlopnév a feltöltött Excel szerint módosítandó
                self.orvosok[nev] = {
                    'preferalt_napok': [],  # Ez is a feltöltött Excel oszlopai szerint módosítandó
                    'ugyeletek_szama': 0
                }
                self.maximum_ugyeletek[nev] = 5  # Alapértelmezett érték, módosítható
                
            return True
        except Exception as e:
            st.error(f"Hiba az Excel beolvasása során: {str(e)}")
            return False
            
    def kivetel_hozzaadas(self, orvos, datum, ok):
        """Kivétel hozzáadása (szabadság, egyéb elfoglaltság)"""
        if orvos not in self.kivetelek:
            self.kivetelek[orvos] = {}
        self.kivetelek[orvos][datum] = ok
        
    def orvos_elerheto(self, orvos, datum):
        """Ellenőrzi, hogy az orvos elérhető-e az adott napon"""
        # Kivételek ellenőrzése
        if orvos in self.kivetelek and datum in self.kivetelek[orvos]:
            return False
            
        # Maximum ügyeletek számának ellenőrzése
        if self.orvosok[orvos]['ugyeletek_szama'] >= self.maximum_ugyeletek[orvos]:
            return False
            
        return True
        
    def beosztas_generalas(self, ev, honap):
        """Havi beosztás generálása"""
        napok_szama = calendar.monthrange(ev, honap)[1]
        beosztas = {}
        
        for nap in range(1, napok_szama + 1):
            datum = f"{ev}-{honap:02d}-{nap:02d}"
            elerheto_orvosok = [
                orvos for orvos in self.orvosok.keys()
                if self.orvos_elerheto(orvos, datum)
            ]
            
            if not elerheto_orvosok:
                st.warning(f"Nem található elérhető orvos: {datum}")
                continue
                
            # Válasszuk ki azt az orvost, akinek a legkevesebb ügyelete van
            valasztott_orvos = min(
                elerheto_orvosok,
                key=lambda x: self.orvosok[x]['ugyeletek_szama']
            )
            
            beosztas[datum] = valasztott_orvos
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
        ev = st.selectbox("Év", range(datetime.now().year, datetime.now().year + 2))
    with col2:
        honap = st.selectbox("Hónap", range(1, 13))
    
    # Kivételek kezelése
    with st.expander("Kivételek megadása"):
        kivetelek_szoveg = st.text_area(
            "Add meg a kivételeket (pl.: 'Dr. Kiss 2024-01-15 szabadság')",
            help="Soronként egy kivétel. Formátum: 'Név ÉÉÉÉ-HH-NN ok'"
        )
    
    if feltoltott_file and st.button("Beosztás generálása"):
        try:
            # Adatok beolvasása
            df = pd.read_excel(feltoltott_file)
            if generator.excel_beolvasas(df):
                # Kivételek feldolgozása
                if kivetelek_szoveg:
                    for sor in kivetelek_szoveg.split('\n'):
                        if sor.strip():
                            reszek = sor.strip().split()
                            if len(reszek) >= 2:
                                orvos = reszek[0]
                                datum = reszek[1]
                                ok = ' '.join(reszek[2:]) if len(reszek) > 2 else 'nem elérhető'
                                generator.kivetel_hozzaadas(orvos, datum, ok)
                
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
                excel_buffer = pd.ExcelWriter('beosztas.xlsx', engine='openpyxl')
                beosztas_df.to_excel(excel_buffer, sheet_name='Beosztás', index=False)
                statisztika_df.to_excel(excel_buffer, sheet_name='Statisztika', index=False)
                excel_buffer.close()
                
                with open('beosztas.xlsx', 'rb') as f:
                    st.download_button(
                        label="Beosztás letöltése",
                        data=f,
                        file_name=f"ugyeleti_beosztas_{ev}_{honap}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        
        except Exception as e:
            st.error(f"Hiba történt: {str(e)}")
            st.error("Kérlek ellenőrizd az input fájl formátumát és a megadott kivételeket")

if __name__ == "__main__":
    main()