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

    def kivetel_hozzaadas(self, szoveg):
        """Kivételek feldolgozása a felhasználói szövegből"""
        if not szoveg:
            return
            
        for sor in szoveg.split('\n'):
            if not sor.strip():
                continue
                
            try:
                # Szöveg szétbontása
                szavak = sor.strip().split()
                if len(szavak) < 2:
                    continue
                
                # Név feldolgozása (első szó vagy Dr.-ral kezdődő rész)
                nev_vege = 1
                if szavak[0].startswith('Dr'):
                    nev_vege = 2
                orvos_nev = ' '.join(szavak[:nev_vege])
                
                # Dátum feldolgozása
                datum = None
                datum_index = nev_vege
                
                # Különböző dátumformátumok kezelése
                while datum_index < len(szavak) and not datum:
                    try:
                        # ÉÉÉÉ-HH-NN vagy ÉÉÉÉ.HH.NN formátum
                        datum_str = szavak[datum_index].replace('.', '-')
                        datum = datetime.strptime(datum_str, '%Y-%m-%d')
                        break
                    except ValueError:
                        try:
                            # NN-HH-ÉÉÉÉ vagy NN.HH.ÉÉÉÉ formátum
                            datum_str = szavak[datum_index].replace('.', '-')
                            datum = datetime.strptime(datum_str, '%d-%m-%Y')
                            break
                        except ValueError:
                            datum_index += 1
                
                if not datum and datum_index + 2 < len(szavak):
                    # Magyar hónapnév formátum kezelése
                    honapok = {
                        'január': 1, 'február': 2, 'március': 3, 'április': 4,
                        'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
                        'szeptember': 9, 'október': 10, 'november': 11, 'december': 12,
                        'jan': 1, 'feb': 2, 'már': 3, 'ápr': 4, 'máj': 5, 'jún': 6,
                        'júl': 7, 'aug': 8, 'szept': 9, 'okt': 10, 'nov': 11, 'dec': 12
                    }
                    
                    try:
                        ev = int(szavak[datum_index])
                        honap = honapok.get(szavak[datum_index + 1].lower())
                        nap = int(szavak[datum_index + 2])
                        if honap:
                            datum = datetime(ev, honap, nap)
                            datum_index += 3
                    except (ValueError, KeyError, IndexError):
                        pass
                
                if not datum:
                    st.warning(f"Nem sikerült feldolgozni a dátumot ebben a sorban: {sor}")
                    continue
                
                # Indok feldolgozása (a maradék szöveg)
                indok = ' '.join(szavak[datum_index + 1:]) if datum_index + 1 < len(szavak) else 'nem elérhető'
                
                # Kivétel hozzáadása
                self.felhasznaloi_kivetelek.append((
                    orvos_nev,
                    datum.strftime('%Y-%m-%d'),
                    indok
                ))
                
            except Exception as e:
                st.warning(f"Hiba a sor feldolgozása során: {sor} - {str(e)}")
                continue

    def elerheto_orvosok(self, datum):
        """Visszaadja az adott napon elérhető orvosokat"""
        ev = datum.year
        honap = datum.month
        nap = datum.day
        datum_str = datum.strftime('%Y-%m-%d')
        
        elerheto = []
        for orvos in self.orvosok:
            # Ellenőrizzük a felhasználói kivételeket
            kivetel_talalat = False
            for kivetel in self.felhasznaloi_kivetelek:
                if kivetel[0] == orvos and kivetel[1] == datum_str:
                    kivetel_talalat = True
                    break
            
            if kivetel_talalat:
                continue
            
            # Ellenőrizzük az Excel-ben megadott kéréseket
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
                try:
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
                except Exception as e:
                    st.error(f"Hiba történt az Excel exportálása során: {str(e)}")
                finally:
                    output_buffer.close()
                    
        except Exception as e:
            st.error(f"Hiba történt: {str(e)}")
            st.error("Kérlek ellenőrizd az input fájl formátumát")

if __name__ == "__main__":
    main()