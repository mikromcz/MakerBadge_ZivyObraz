# Integrace MakerBadge a služby Živý obraz v CircuitPython

Pirátský (alternativní) firmware pro službu [Živý obraz](https://zivyobraz.eu/), která umožňuje vytvářet vlastní dashboardy primárně určené pro E-Ink displeje.

Je odladěn pro vývojovou desku [**MakerBadge**](https://www.makermarket.cz/maker-badge/), který používá ESP32-S2 a B/W E-Ink 250x122px.

Oproti originálnímu C++ firmware je tato integrace psána v [**CircuitPython**](https://circuitpython.org/) a tak **nevyžaduje žádnou kompilaci** - stačí nahrát [CircuitPyhton](https://circuitpython.org/board/maker_badge/) a zdrojový skript na připojený [MakerBadge](https://www.makermarket.cz/maker-badge/).

API služby [Živý obraz](https://zivyobraz.eu/) vrací obrázek nakonfigurovaného dashboardu ve formátu BMP (v1) nebo komprimovaný RLE (v2.0) a v HTTP hlavičkách předává informaci kdy došlo k poslední změně na dashboardu (a je tak třeba display překreslit) a na jak dlouho má deska přejít do Deep Sleep módu.

Timestamp poslední změny se ukládá do NVM, takže je uchován i po vzbuzení z Deep Sleep a restartu. Pro jednoduchost zde stačí pouze kontrolovat, zda se timestamp změnil a není třeba pracovat s reálným časem.

Pro ušetření zdrojů a opravy stavu, kdy mi služba vracela před samotnými daty BMP souboru řetězec "Neplané ID", je implementován vlastní jednoduchý parser BMP souboru.

Pro novou verzi 2.0 je implementován RLE parser, který kontroluje, že hlavička vrácených dat je Z2 (https://wiki.zivyobraz.eu/doku.php?id=portal:format_z1_a_z2). Kód používá streamovaného HTTP přenosu.

Práce s API, parsování obrázku a zobrazování na E-Ink je v souboru *code.py*, v souboru *mb_setup.py* je obecné nastavení periferií MakerBadge a několik pomocných funkcí. V souboru *settings.toml* se nastavuje připojení k WiFi.

- MakerBadge:
  - https://www.makermarket.cz/maker-badge/
  - https://github.com/makerfaireczech/maker_badge
- Živý obraz:
  - https://zivyobraz.eu/
  - https://github.com/MultiTricker/zivyobraz-fw
- CircuitPython: https://circuitpython.org/board/maker_badge/

## Poznámky
- Kód je sice nyní kompatibilní s CircuitPython 9x, ale ve verzích 9.0.0, 9.0.4, 9.0.5, 9.1.0b3 se zobrazuje v horní části displeje šmouha co nezmizí. S CP 8.x funguje vše jak má (Zkoušeno s 8.2.6 a 8.2.10)
  
  | CircuitPython 8.x | CircuitPython 9.x |
  |-------------------|-------------------|
  | <img src="./assets/MakerBadgeCircuitPython8.x.jpeg" alt="CircuitPython8.x" width="300px"> | <img src="./assets/MakerBadgeCircuitPython9.x.jpeg" alt="CircuitPython9.x" width="300px"> |

- [Živý obraz](https://zivyobraz.eu/) mi občas vrací BMP s 24 bitovou hloubkou, a s tím si skript neporadí (`MemoryError: memory allocation failed, allocating 67108864 bytes`)
- Displej je asi GDEM0213B74, 4 stupně šedi - lze tedy zkusit color "BW" i "4G"


## Další ukázky s MakerBadge:
- [Interaktivní visačka s QR vstupenkou](https://github.com/MakerClassCZ/Events/tree/main/2023-09-15-PyconCZ/badge)
