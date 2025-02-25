import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import calendar
import re
import io

class UgyeletiBeosztasGenerator:
    def __init__(self):
        self.orvosok = {}
        self.keresek = {}  # {év: {hónap: {orvos: {nap: státusz}}}}
        self.felhasznaloi_kivetelek = []  # [(orvos, datum, indok)]
        self.weekday_exceptions = {}   # {orvos: [engedélyezett hét napok (0-6)]}
        self.pairing_constraints = []  # [(orvos1, orvos2)]
        
    def excel_beolvasas(self, file_content):
        """Excel tartalom feldolgozása memóriából"""
        try:
            excel_buffer = io.BytesIO(file_content)
            xls = pd.ExcelFile(excel_buffer)
            
            for sheet_name in xls.sheet_names:
                # Év és hónap meghatározása a munkalap nevéből
                if sheet_name.startswith('25 '):
                    ev = 2025
                    honap = sheet_name.split(' ')[1].lower()
                else:
                    ev = 2024
                    honap = sheet_name.lower()
                
                honapok = {
                    'január': 1, 'február': 2, 'március': 3, 'április': 4,
                    'május': 5, 'június': 6, 'július': 7, 'augusztus': 8,
                    'szeptember': 9, 'október': 10, 'november': 11, 'december': 12
                }
                honap_szam = honapok.get(honap)
                
                if honap_szam:
                    df = pd.read_excel(excel_buffer, sheet_name=sheet_name)
                    orvos_oszlop = df.columns[0]
                    
                    for index, row in df.iterrows():
                        orvos_nev = row[orvos_oszlop]
                        if pd.notna(orvos_nev) and isinstance(orvos_nev, str):
                            if orvos_nev not in self.orvosok:
                                self.orvosok[orvos_nev] = {
                                    'nev': orvos_nev,
                                    'ugyeletek_szama': 0
                                }
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
            excel_buffer.close()
            return True
            
        except Exception as e:
            st.error(f"Hiba az Excel beolvasása során: {str(e)}")
            return False

    def kivetel_hozzaadas(self, szoveg):
        """Kivételek feldolgozása a felhasználói szövegből"""
        if not szoveg:
            return
            
        # Töröljük a meglévő kivételeket az új feldolgozás előtt
        self.felhasznaloi_kivetelek = []
        self.weekday_exceptions = {}
        self.pairing_constraints = []
            
        for sor in szoveg.split('\n'):
            if not sor.strip():
                continue
                
            try:
                szavak = sor.strip().split()
                if len(szavak) < 2:
                    continue
                
                # Az orvos neve (ha "Dr" szerepel, két szóból)
                nev_vege = 1
                if szavak[0].startswith('Dr'):
                    nev_vege = 2
                orvos_nev = ' '.join(szavak[:nev_vege])
                
                # Ha a sorban "nem dolgozhat" szerepel, akkor párosítási korlátozásról van szó
                if "nem dolgozhat" in sor.lower():
                    # Például: "Dr Kormos Ágnes nem dolgozhat Dr. Forró Tímeával."
                    match = re.search(r'(?i)nem dolgozhat\s+(Dr\.?\s+\S+\s+\S+)', sor)
                    if match:
                        masodik_orvos = match.group(1).strip()
                        self.pairing_constraints.append((orvos_nev, masodik_orvos))
                    else:
                        st.warning(f"Nem sikerült feldolgozni a párosítási kivételt ebben a sorban: {sor}")
                    continue  # Ebben az esetben nem folytatjuk a további dátumfeldolgozást
                
                # Ha a sorban "csak" szerepel, illetve hétnapok (pl. "hétfőn") is, akkor hétköznapi kivételről van szó
                if "csak" in sor.lower():
                    # Magyar hét napjainak leképezése
                    weekday_mapping = {
                        'hétfő': 0,
                        'kedd': 1,
                        'szerda': 2,
                        'csütörtök': 3,
                        'péntek': 4,
                        'szombat': 5,
                        'vasárnap': 6
                    }
                    allowed_weekdays = []
                    for szo in szavak:
                        # Tisztítjuk a szót az írásjelektől
                        clean_word = re.sub(r'[.,]', '', szo).lower()
                        # Ha a szó végén "-n" szerepel (pl. "hétfőn"), eltávolítjuk
                        if clean_word.endswith('n'):
                            base = clean_word[:-1]
                        else:
                            base = clean_word
                        if base in weekday_mapping:
                            allowed_weekdays.append(weekday_mapping[base])
                    if allowed_weekdays:
                        self.weekday_exceptions[orvos_nev] = allowed_weekdays
                        continue  # Ezt a sort így feldolgoztuk
                    
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
    
    def _parse_simple_date(self, szavak):
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

    def elerheto_orvosok(self, datum):
        """Visszaadja az adott napon elérhető orvosokat"""
        ev = datum.year
        honap = datum.month
        nap = datum.day
        datum_str = datum.strftime('%Y-%m-%d')
        
        elerheto = []
        for orvos in self.orvosok:
            # Ellenőrizzük a dátumra vonatkozó kivételeket
            kivetel_talalat = False
            for kivetel in self.felhasznaloi_kivetelek:
                if kivetel[0] == orvos and kivetel[1] == datum_str:
                    kivetel_talalat = True
                    break
            if kivetel_talalat:
                continue
            # Ha van hétnapi kivétel, akkor csak az engedélyezett napokon lehet elérhető
            if orvos in self.weekday_exceptions:
                allowed = self.weekday_exceptions[orvos]
                if datum.weekday() not in allowed:
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

    def can_pair(self, doc1, doc2):
        """Ellenőrzi, hogy két orvos párosítható-e egymással"""
        for a, b in self.pairing_constraints:
            if (doc1 == a and doc2 == b) or (doc1 == b and doc2 == a):
                return False
        return True
    
    def beosztas_generalas(self, ev, honap):
        """Havi beosztás generálása két orvossal naponta"""
        napok_szama = calendar.monthrange(ev, honap)[1]
        beosztas = {}
        
        for nap in range(1, napok_szama + 1):
            datum = datetime(ev, honap, nap)
            datum_str = datum.strftime('%Y-%m-%d')
            elerheto_orvosok = self.elerheto_orvosok(datum)
            
            if len(elerheto_orvosok) < 2:
                st.warning(f"Nem található elegendő elérhető orvos: {datum_str} (minimum 2 szükséges)")
                beosztas[datum_str] = []
                continue
            
            # Első orvos kiválasztása
            first = min(
                elerheto_orvosok,
                key=lambda x: self.orvosok[x]['ugyeletek_szama']
            )
            
            # Második orvos kiválasztása, a párosítási korlátozást figyelembe véve
            remaining = [doc for doc in elerheto_orvosok if doc != first and self.can_pair(first, doc)]
            if not remaining:
                st.warning(f"Nincs megfelelő második orvos a {datum_str} napon {first} esetében a párosítási kivétel miatt")
                beosztas[datum_str] = [first]
                self.orvosok[first]['ugyeletek_szama'] += 1
                continue
            
            second = min(
                remaining,
                key=lambda x: self.orvosok[x]['ugyeletek_szama']
            )
            
            beosztas[datum_str] = [first, second]
            self.orvosok[first]['ugyeletek_szama'] += 1
            self.orvosok[second]['ugyeletek_szama'] += 1
        
        return beosztas

def main():
    st.set_page_config(page_title="Ügyeleti Beosztás Generáló", layout="wide")
    st.title("Ügyeleti Beosztás Generáló")
    
    # Ellenőrizzük, hogy a session state-ben lévő generator objektum helyes-e,
    # ha nincs, vagy nem rendelkezik az excel_beolvasas metódussal, akkor új példányt készítünk.
    if 'generator' not in st.session_state or not hasattr(st.session_state.generator, 'excel_beolvasas'):
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
        - Dr. Kormos Ágnes csak hétfőn tud dolgozni meg szerdán.
        - Dr. Kormos Ágnes nem dolgozhat Dr. Forró Tímeával.
        """)
        kivetelek_szoveg = st.text_area(
            "Írja be a kivételeket", 
            help="Soronként egy kivétel: adja meg az orvos nevét, a dátumot vagy a napokat, illetve az indokot, illetve a párosítási korlátozást."
        )
    
    if feltoltott_file is not None and st.button("Beosztás generálása"):
        file_content = feltoltott_file.read()
        if st.session_state.generator.excel_beolvasas(file_content):
            st.success("Excel adatok sikeresen beolvasva!")
            
            if kivetelek_szoveg:
                st.session_state.generator.kivetel_hozzaadas(kivetelek_szoveg)
            
            beosztas = st.session_state.generator.beosztas_generalas(ev, honap)
            
            st.subheader("Generált beosztás")
            beosztas_lista = []
            for datum, orvosok in beosztas.items():
                beosztas_lista.append({
                    'Dátum': datum,
                    'Első Orvos': orvosok[0] if len(orvosok) > 0 else None,
                    'Második Orvos': orvosok[1] if len(orvosok) > 1 else None
                })
            
            beosztas_df = pd.DataFrame(beosztas_lista)
            beosztas_df = beosztas_df.sort_values('Dátum')
            st.dataframe(beosztas_df, width=1000, height=600)
            
            if st.session_state.generator.felhasznaloi_kivetelek or st.session_state.generator.weekday_exceptions or st.session_state.generator.pairing_constraints:
                st.subheader("Feldolgozott kivételek")
                extra_info = {
                    'Kivételes dátumok': st.session_state.generator.felhasznaloi_kivetelek,
                    'Hétköznapi kivételek': st.session_state.generator.weekday_exceptions,
                    'Párosítási korlátozások': st.session_state.generator.pairing_constraints
                }
                kivetelek_df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in extra_info.items()]))
                st.dataframe(kivetelek_df, width=1000, height=600)
            
            st.subheader("Ügyeletek statisztikája")
            statisztika_df = pd.DataFrame(
                [(nev, adatok['ugyeletek_szama']) 
                 for nev, adatok in st.session_state.generator.orvosok.items()],
                columns=['Orvos', 'Ügyeletek száma']
            )
            st.dataframe(statisztika_df, width=600, height=300)
            
            # Excel exportálás
            output_buffer = io.BytesIO()
            try:
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    beosztas_df.to_excel(writer, sheet_name='Beosztás', index=False)
                    statisztika_df.to_excel(writer, sheet_name='Statisztika', index=False)
                    if st.session_state.generator.felhasznaloi_kivetelek or st.session_state.generator.weekday_exceptions or st.session_state.generator.pairing_constraints:
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
        else:
            st.error("Kérlek ellenőrizd az input fájl formátumát")


   # Footer hozzáadása
    st.markdown("""
    <div style='text-align: center; margin-top: 50px;'>
         ❤️ készítve - Kapcsolat <a href="mailto:info@albhu.hu">Avni Hafuzi</a>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
