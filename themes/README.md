# Optionale gomuks-Themes

## Salbei & Stein

`salbei-und-stein.css` verwendet die Farben des gleichnamigen Home-Assistant-Themes: salbeigrüne Akzente, helle Steinflächen beziehungsweise dunkle grüngraue Flächen, Systemschrift und die Zuhause-Formensprache: schattenfreie 24-px-Karten auf großen Displays, ruhige Nachrichtenflächen, runde Bedienelemente, 22-px-Raumüberschriften sowie 15/13-px-Texthierarchie. Die Gestaltung ist auf die gomuks-CSS-Variablen des im Add-on verwendeten Commits abgestimmt. Noch nicht am laufenden Client visuell abgenommen.

In gomuks die Einstellungen öffnen und nach **Custom CSS** suchen. Bestehendes CSS bei Bedarf sichern, anschließend den vollständigen Dateiinhalt einfügen und übernehmen. Kein Add-on-Neubau notwendig. Zum Rückgängigmachen den eingefügten Inhalt entfernen.

Standardmäßig folgt Hell/Dunkel der Browser-/Systemeinstellung. Das ist keine automatische Synchronisierung mit dem HA-Benutzerprofil. Bei einem in HA manuell gewählten Modus im CSS `color-scheme: light dark;` durch `color-scheme: light;` oder `color-scheme: dark;` ersetzen.

Keine externen CSS-/Schrift-Downloads. Weder Zugriffsschutz noch Matrix-Daten werden verändert. Farbwerte stammen aus der lokalen HA-Theme-Referenz; gomuks-Variablen siehe https://github.com/gomuks/gomuks/blob/b1ba2099e9d4c0068c7e614d7141b001848369c5/web/src/index.css.


### Layout-Erweiterung vom 27.10.2026

Die CSS-Datei umfasst jetzt Farben **und Layout**. Den bisherigen Inhalt in Custom CSS vollständig ersetzen. Auf großen Displays bekommen Seitenleiste und Chat getrennte abgerundete Flächen; auf kleinen Displays bleiben gomuks' native Navigation und volle Panelbreite erhalten. Nachrichten erhalten weiche Flächen, der Composer eine 24-px-Rundung und 44-px-Iconbuttons. Zeilenhöhen der virtualisierten Raumliste bleiben unverändert. Fokusmarkierung, Fehler-/Erwähnungszustände, Reaktionen und Zustellanzeigen werden nicht ausgeblendet.

Selektoren wurden gegen MainScreen.css, RoomList.css, RoomView.css, RoomViewHeader.css, MessageComposer.css und TimelineEvent.css des festgelegten gomuks-Commits geprüft. CSS-Struktur auf ausgeglichene Klammern geprüft; keine visuelle Abnahme am echten Client. Nach Einfügen besonders lange Texte, Anhänge, Antworten, Raumwechsel, Tastaturfokus und Handyansicht prüfen. Die CSS-Datei enthält keine automatische Übernahme des HA-Profil-Themes.
