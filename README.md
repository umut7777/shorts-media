# shorts-media

Generator und Zwischenspeicher für Umuts YouTube-Shorts **„Which Color Wins?“**:
vier Bälle mit Gesichtern brechen aus 14 rotierenden Ringen aus, jeder zerbrochene Ring
ist ein Punkt. Grafik, Physik, Musik und Sounds werden komplett per Code erzeugt
(keine fremden Bilder, Clips oder Musik).

## Ablauf (tägliche geplante Aufgabe)

1. `generator/make_short.py` erzeugt pro Tag zwei Videos. Farben, Thema, Titel und Musik
   ergeben sich aus dem Datum; aus Tausenden simulierten Rennen wird das spannendste
   gewählt (Gleichstand vor dem letzten Ring, Führungswechsel, schneller Start).
2. `generator/publish.py upload` legt die Videos auf einen neuen Branch `upload-JJJJ-MM-TT`,
   damit Metricool sie über einen öffentlichen Link abrufen kann.
3. Die Aufgabe legt die Videos in Metricool als **Entwürfe** an. Veröffentlicht wird erst,
   wenn Umut sie in Metricool einplant.

## Aufräumen

Metricool kopiert die Videos beim Anlegen des Entwurfs auf seine eigenen Server.
Alte `upload-…`-Branches können deshalb jederzeit gelöscht werden:
<https://github.com/umut7777/shorts-media/branches>

## Lokal ausführen

```bash
pip install pycairo numpy scipy pillow   # ffmpeg muss installiert sein
python3 generator/make_short.py --date 2026-10-25 --count 1 --out videos
```

Schrift: Lilita One (SIL Open Font License, siehe `generator/fonts/OFL.txt`).
