import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import re
import io
from typing import Dict, List, Tuple, Optional, Any
from functools import lru_cache

class UgyeletiBeosztasGenerator:
    def __init__(self):
        self.orvosok: Dict[str, Dict[str, Any]] = {}  # {orvosnév: {'nev': orvosnév, 'ugyeletek_szama': számláló}}
        self.keresek: Dict[int, Dict[int, Dict[str, Dict[int, str]]]] = {}  # {év: {hónap: {orvos: {nap: státusz}}}}
        self.felhasznaloi_kivetelek: List[Tuple[str, str, str]] = []  # [(orvos, dátum, indok)]
        
def excel_beolvasas(self, file_content):
    """Excel tartalom feldolgozása memóriából"""
    try:
        # Excel fájl beolvasása memóriából, explicit encoding megadásával
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
                # Munkalap beolvasása explicit encoding és engine megadásával
                df = pd.read_excel(
                    excel_buffer, 
                    sheet_name=sheet_name,
                    engine='openpyxl',
                    encoding='utf-8'
                )
                
                # Az első oszlop az orvosok neveit tartalmazza
                orvos_oszlop = df.columns[0]
                
                # Orvosok és kéréseik feldolgozása
                for index, row in df.iterrows():
                    orvos_nev = str(row[orvos_oszlop]).strip()  # Explicit string konverzió és whitespace eltávolítás
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
                                    
                                    self.keresek[ev][honap_szam][orvos_nev][nap] = str(status)  # Explicit string konverzió
        
        excel_buffer.close()
        return True
        
    except Exception as e:
        st.error(f"Hiba az Excel beolvasása során: {str(e)}")
        return False

    def kivetel_hozzaadas(self, szoveg: str) -> None:
        """Kivételek feldolgozása a felhasználói szövegből"""
        if not szoveg:
            return
            
        for sor in szoveg.split('\n'):
            if not sor.strip():
                continue
                
            try:
                szavak = sor.strip().split()
                if len(szavak) < 2:
                    continue
                
                nev_vege = 1
                if szavak[0].startswith('Dr'):
                    nev_vege = 2
                orvos_nev = ' '.join(szavak[:nev_vege])
                
                datum_kezdet = None
                datum_veg = None
                datum_index = nev_vege
                
                tartomany_match = None
                for i, szo in enumerate(szavak[datum_index:], datum_index):
                    if "között" in szo or "-" in szo:
                        tartomany_text = ' '.join(szavak[datum_index:i+2])
                        mintak = [
                            r'(\d{1,2})[.-](\d{1,2})',
                            r'(\d{1,2})\s*(?:és|-)?\s*(\d{1,2})\s+között',
                            r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})\s*(?:és|-)?\s*(\d{4})[.-](\d{1,2})[.-](\d{1,2})'
                        ]
                        
                        for minta in mintak:
                            match = re.search(minta, tartomany_text)
                            if match:
                                tartomany_match = match
                                datum_index = i
                                break
                        if tartomany_match:
                            break
                
                if tartomany_match:
                    honapok = {
                        'január': 1, 'február': 2, 'március': 3, 'április': 4,
                        'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
                        'szeptember': 9, 'október': 10, 'november': 11, 'december': 12,
                        'jan': 1, 'feb': 2, 'már': 3, 'ápr': 4, 'máj': 5, 'jún': 6,
                        'júl': 7, 'aug': 8, 'szept': 9, 'okt': 10, 'nov': 11, 'dec': 12
                    }
                    
                    honap = None
                    ev = datetime.now().year
                    for szo in szavak[:datum_index]:
                        if szo.lower() in honapok:
                            honap = honapok[szo.lower()]
                        elif szo.isdigit() and len(szo) == 4:
                            ev = int(szo)
                    
                    if honap is None:
                        raise ValueError("Nem található hónap megjelölés")
                    
                    if len(tartomany_match.groups()) == 2:
                        nap_kezdet = int(tartomany_match.group(1))
                        nap_veg = int(tartomany_match.group(2))
                        datum_kezdet = datetime(ev, honap, nap_kezdet)
                        datum_veg = datetime(ev, honap, nap_veg)
                    elif len(tartomany_match.groups()) == 6:
                        datum_kezdet = datetime(
                            int(tartomany_match.group(1)),
                            int(tartomany_match.group(2)),
                            int(tartomany_match.group(3))
                        )
                        datum_veg = datetime(
                            int(tartomany_match.group(4)),
                            int(tartomany_match.group(5)),
                            int(tartomany_match.group(6))
                        )
                else:
                    datum_kezdet = self._parse_simple_date(szavak[datum_index:])
                    if datum_kezdet:
                        datum_veg = datum_kezdet
                
                if not datum_kezdet or not datum_veg:
                    st.warning(f"Nem sikerült feldolgozni a dátumot ebben a sorban: {sor}")
                    continue
                
                indok_szavak = []
                for szo in szavak[datum_index+1:]:
                    if not any(k in szo.lower() for k in ['között', 'és']):
                        indok_szavak.append(szo)
                indok = ' '.join(indok_szavak) if indok_szavak else 'nem elérhető'
                
                aktualis_datum = datum_kezdet
                while aktualis_datum <= datum_veg:
                    self.felhasznaloi_kivetelek.append((
                        orvos_nev,
                        aktualis_datum.strftime('%Y-%m-%d'),
                        indok
                    ))
                    aktualis_datum += timedelta(days=1)
                
            except Exception as e:
                st.warning(f"Hiba a sor feldolgozása során: {sor} - {str(e)}")
                continue
    
    def _parse_simple_date(self, szavak: List[str]) -> Optional[datetime]:
        """Egyszerű dátum feldolgozása"""
        honapok = {
            'január': 1, 'február': 2, 'március': 3, 'április': 4,
            'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
            'szeptember': 9, 'október': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'már': 3, 'ápr': 4, 'máj': 5, 'jún': 6,
            'júl': 7, 'aug': 8, 'szept': 9, 'okt': 10, 'nov': 11, 'dec': 12
        }
        
        try:
            for i, szo in enumerate(szavak):
                try:
                    datum_str = szo.replace('.', '-')
                    return datetime.strptime(datum_str, '%Y-%m-%d')
                except ValueError:
                    pass
                
                try:
                    datum_str = szo.replace('.', '-')
                    return datetime.strptime(datum_str, '%d-%m-%Y')
                except ValueError:
                    pass
                
                if i + 2 < len(szavak):
                    try:
                        ev = int(szavak[i])
                        honap = honapok.get(szavak[i + 1].lower())
                        nap = int(szavak[i + 2])
                        if honap:
                            return datetime(ev, honap, nap)
                    except (ValueError, KeyError, IndexError):
                        pass
        except Exception:
            return None
        
        return None

    @lru_cache(maxsize=128)
    def elerheto_orvosok(self, datum: datetime) -> List[str]:
        """
        Visszaadja az adott napon elérhető orvosokat,
        figyelembe véve a felhasználói kivételeket és az Excel-ben megadott kéréseket.
        """
        ev = datum.year
        honap = datum.month
        nap = datum.day
        datum_str = datum.strftime('%Y-%m-%d')
        
        elerheto = []
        for orvos in self.orvosok:
            kivetel_talalat = False
            for kivetel in self.felhasznaloi_kivetelek:
                if kivetel[0] == orvos and kivetel[1] == datum_str:
                    kivetel_talalat = True
                    break
            
            if kivetel_talalat:
                continue
            
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
    
    def beosztas_generalas(self, ev: int, honap: int) -> Dict[str, List[str]]:
        """Havi beosztás generálása, ahol egy nap két orvosnak kell dolgoznia"""
        napok_szama = calendar.monthrange(ev, honap)[1]
        beosztas = {}
        
        # Pre-calculate available doctors for optimization
        napi_elerheto_orvosok = {
            nap: self.elerheto_orvosok(datetime(ev, honap, nap))
            for nap in range(1, napok_szama + 1)
        }
        
        # Sort days by number of available doctors
        rendezett_napok = sorted(
            range(1, napok_szama + 1),
            key=lambda x: len(napi_elerheto_orvosok[x])
        )
        
        for nap in rendezett_napok:
            datum = datetime(ev, honap, nap)
            elerheto_orvosok = napi_elerheto_orvosok[nap]
            
            if len(elerheto_orvosok) < 2:
                st.warning(f"Nem található két elérhető orvos a(z) {datum.strftime('%Y-%m-%d')} napra!")
                continue
            
            valasztott_orvosok = sorted(
                elerheto_orvosok,
                key=lambda x: self.orvosok[x]['ugyeletek_szama']
            )[:2]
            
            beosztas[datum.strftime('%Y-%m-%d')] = valasztott_orvosok
            
            for orvos in valasztott_orvosok:
                self.orvosok[orvos]['ugyeletek_szama'] += 1
        
        return beosztas

def main():
    st.set_page_config(page_title="Ügyeleti Beosztás Generáló", layout="wide")
    st.title("Ügyeleti Beosztás Generáló")
    
    if 'generator' not in st.session_state:
        st.session_state.generator = UgyeletiBeosztasGenerator()
    
    feltoltott_file = st.file_uploader("Ügyeleti kérések Excel feltöltése", type=["xlsx"])
    
    col1, col2 = st.columns(2)
    with col1:
        ev = st.selectbox("Év", [2024, 2025])
    with col2:
        honap = st.selectbox("Hónap", list(range(1, 13)))
    
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
            file_content = feltoltott_file.read()
            
            if st.session_state.generator.excel_beolvasas(file_content):
                st.success("Excel adatok sikeresen beolvasva!")
                
                if kivetelek_szoveg:
                    st.session_state.generator.kivetel_hozzaadas(kivetelek_szoveg)
                
                beosztas = st.session_state.generator.beosztas_generalas(ev, honap)
                
                st.subheader("Generált beosztás")
                beosztas_df = pd.DataFrame(
                    [(datum, ", ".join(orvosok)) for datum, orvosok in beosztas.items()],
                    columns=['Dátum', 'Orvosok']
                )
                beosztas_df = beosztas_df.sort_values('Dátum')
                st.dataframe(
                    beosztas_df,
                    height=400,
                    width=800,
                    hide_index=True
                )
                
                if st.session_state.generator.felhasznaloi_kivetelek:
                    st.subheader("Feldolgozott kivételek")
                    kivetelek_df = pd.DataFrame(
                        list(set(st.session_state.generator.felhasznaloi_kivetelek)),
                        columns=['Orvos', 'Dátum', 'Indok']
                    )
                    st.dataframe(
                        kivetelek_df,
                        height=300,
                        width=800,
                        hide_index=True
                    )
                
                st.subheader("Ügyeletek statisztikája")
                statisztika_df = pd.DataFrame(
                    [(nev, adatok['ugyeletek_szama']) 
                     for nev, adatok in st.session_state.generator.orvosok.items()],
                    columns=['Orvos', 'Ügyeletek száma']
                )
                st.dataframe(
                    statisztika_df,
                    height=200,
                    width=600,
                    hide_index=True
                )
                
                output_buffer = io.BytesIO()
                try:
                    with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                        beosztas_df.to_excel(writer, sheet_name='Beosztás', index=False)
                        statisztika_df.to_excel(writer, sheet_name='Statisztika', index=False)
                        if st.session_state.generator.felhasznaloi_kivetelek:
                            kivetelek_df = pd.DataFrame(
                                list(set(st.session_state.generator.felhasznaloi_kivetelek)),
                                columns=['Orvos', 'Dátum', 'Indok']
                            )
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