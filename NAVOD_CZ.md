# Duplicate Files – návod (CZ)

Bezpečné hledání duplicitních souborů pro macOS (Apple Silicon, M1 a novější). Jazyk aplikace přepneš vpravo nahoře (🌐 EN / CZ), výchozí je angličtina.

## Instalace

Otevři Terminál a vlož tento příkaz:

```
curl -fsSL https://raw.githubusercontent.com/Luboshort/Duplicate-files/main/install.sh | bash
```

Stáhne nejnovější verzi, nainstaluje ji do složky Aplikace (bez práv správce do `~/Applications`) a spustí.

**Proč ne stažením DMG v prohlížeči:** soubor stažený prohlížečem dostane od macOS značku „staženo z internetu“. Aplikace bez placeného podpisu Apple se pak zablokuje s varováním o možném malwaru a na firemních Macech ji často nejde ani povolit. Soubor stažený z Terminálu tuto značku nedostane.

## Aktualizace

Aplikace zkontroluje GitHub při spuštění a pak jednou denně. Když je nová verze, nabídne **Nainstalovat a restartovat**: na pozadí proběhne stejná instalace a aplikace se spustí znovu.

Kdykoli můžeš také znovu spustit příkaz výše. Ruční kontrola je v menu ⚙ → *Zkontrolovat aktualizace…*, kde jde automatickou kontrolu i vypnout.

## Odinstalace

Přetáhni `DuplicateFiles.app` ze složky Aplikace do Koše. Nastavení zůstane v `~/Library/Application Support/DuplicitniSoubory/`.

## Sestavení ze zdrojových kódů

Potřebuješ Python z [python.org](https://www.python.org/downloads/macos/). Systémový Python od Applu má zastaralé Tk a okno by zůstalo prázdné.

```bash
bash build.sh
```

Výsledek je `~/Applications/DuplicateFiles.app` a `~/Desktop/DuplicateFiles-x.y.dmg`.

## Vydání nové verze

1. V `app.py` zvyš `APP_VERSION`.
2. Do `CHANGELOG.md` přidej sekci s novou verzí.
3. Spusť `bash publish.sh`.

Skript potřebuje `git` (`xcode-select --install`) a GitHub CLI (`brew install gh`). Sestaví aplikaci, nahraje kód a vytvoří vydání s `DuplicateFiles.dmg`. Odtud ji stahuje `install.sh` i aktualizace v aplikaci.
