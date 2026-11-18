# Duplicate Files – návod (CZ)

Jazyk aplikace přepneš vpravo nahoře (🌐 EN / CZ). Výchozí je angličtina.

## Instalace hotové aplikace

1. Stáhni z [Releases](https://github.com/Luboshort/Duplicate-files/releases/latest) soubor **DuplicateFiles-x.y.dmg**.
2. Otevři ho a přetáhni aplikaci do složky Aplikace.
3. Při prvním spuštění macOS hlásí, že aplikaci nemůže ověřit: *Hotovo* → *Nastavení systému → Soukromí a zabezpečení* → *Přesto otevřít*. Stačí jednou.

Aplikace při spuštění sama zkontroluje, jestli je na GitHubu nová verze, a nabídne stažení.

## Sestavení ze zdrojových kódů

Potřebuješ Python z [python.org](https://www.python.org/downloads/macos/). Systémový Python od Applu má zastaralé Tk a okno by zůstalo prázdné.

```bash
bash build.sh
```

Výsledek je `~/Applications/DuplicateFiles.app` a `~/Desktop/DuplicateFiles-x.y.dmg`.

## Vydání nové verze na GitHub

1. V `app.py` zvyš `APP_VERSION`.
2. Spusť `bash publish.sh`.

Skript potřebuje `git` (`xcode-select --install`) a GitHub CLI (`brew install gh`).
