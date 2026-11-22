# -*- coding: utf-8 -*-
"""Anglické překlady textů aplikace (klíč = český zdrojový text, šablony s {0}, {1:.0f}…)."""

EN = {
    "Duplicitní soubory":
        "Duplicate Files",
    "vlastní":
        "own",
    "Procházím… {0} složek, {1} souborů":
        "Scanning… {0} folders, {1} files",
    "Vyber aspoň jedno kritérium.":
        "Select at least one criterion.",
    "Rychlé porovnání obsahu… {0}/{1} skupin":
        "Quick content comparison… {0}/{1} groups",
    "Ověřuji obsah… {0} z {1}":
        "Verifying content… {0} of {1}",
    "Ponechat nejstarší (datum vytvoření)":
        "Keep oldest (creation date)",
    "Ponechat nejstarší (datum změny)":
        "Keep oldest (modification date)",
    "Ponechat nejnovější (datum změny)":
        "Keep newest (modification date)",
    "Ponechat nejkratší cestu":
        "Keep shortest path",
    "Ponechat nejdelší cestu":
        "Keep longest path",
    "Ponechat soubor ve vybrané složce…":
        "Keep the file in a chosen folder…",
    "síťový nebo neznámý disk – Koš tam nemusí být (soubor by se smazal hned); použij Přesunout do…":
        "network or unknown disk – it may have no Trash (the file would be deleted immediately); use Move to…",
    "nepodařilo se přesunout do Koše":
        "could not move to Trash",
    "🔒 Zamčený soubor":
        "🔒 Locked file",
    "🔒 Zamčená složka":
        "🔒 Locked folder",
    "🔒 Zamčený soubor jiného uživatele":
        "🔒 Locked file owned by another user",
    "🔒 Systémový zámek":
        "🔒 System lock",
    "👤 Bez oprávnění zapisovat do složky":
        "👤 No permission to write to the folder",
    "👤 Soubor jiného uživatele ve sdílené složce":
        "👤 Another user's file in a shared folder",
    "👤 Zakázáno pravidlem ACL":
        "👤 Denied by an ACL rule",
    "👤 Bez oprávnění soubor číst":
        "👤 No permission to read the file",
    "🛡 macOS nepovolil přístup (Plný přístup k disku)":
        "🛡 macOS denied access (Full Disk Access)",
    "⛔ Disk je jen pro čtení":
        "⛔ The disk is read-only",
    "⛔ Chráněno systémem macOS":
        "⛔ Protected by macOS",
    "Soubor už neexistuje":
        "File no longer exists",
    "Jiná chyba":
        "Other error",
    "🛡 Přeskočeno ochranou":
        "🛡 Skipped for safety",
    "Další chyby (podrobně nerozebrány)":
        "More errors (not analysed in detail)",
    "např. disk NTFS z Windows nebo zamčená SD karta":
        "e.g. an NTFS disk from Windows or a locked SD card",
    "vlastník: {0}":
        "owner: {0}",
    "složka {0}, vlastník: {1}":
        "folder {0}, owner: {1}",
    "složka „{0}“ patří: {1}":
        "folder “{0}” belongs to: {1}",
    "vlastník souboru: {0}":
        "file owner: {0}",
    "akce s právy správce selhala":
        "administrator action failed",
    "s právy správce":
        "with administrator rights",
    "je v pomocné složce „{0}“ (nedostal se do Koše) – nic se neztratilo":
        "is in the helper folder “{0}” (did not reach the Trash) – nothing was lost",
    "nepodařilo se ani s právy správce":
        "failed even with administrator rights",
    "celý systémový disk upravovat nelze – vyber konkrétní složku nebo externí disk":
        "the whole system disk cannot be changed – choose a specific folder or an external disk",
    "celou domovskou složku upravovat nelze – vyber v ní konkrétní podsložku":
        "the whole home folder cannot be changed – choose a specific subfolder in it",
    "složka „{0}“ patří systému nebo aplikacím – její práva se nesmí měnit":
        "folder “{0}” belongs to the system or apps – its permissions must not be changed",
    "zálohy Time Machine se upravovat nesmí":
        "Time Machine backups must not be changed",
    "disk obsahuje zálohy Time Machine":
        "the disk contains Time Machine backups",
    "na disku je macOS (nebo jeho data) – vyber v něm konkrétní složku s daty":
        "the disk contains macOS (or its data) – choose a specific data folder on it",
    "složka „{0}“ patří systému – její práva se nesmí měnit":
        "folder “{0}” belongs to the system – its permissions must not be changed",
    "celou domovskou složku ani její Library upravovat nelze – vyber konkrétní podsložku":
        "the whole home folder or its Library cannot be changed – choose a specific subfolder",
    "Kontroluji… {0} položek":
        "Checking… {0} items",
    "Čekám na heslo správce…":
        "Waiting for the administrator password…",
    "Opravuji… {0}/{1}":
        "Fixing… {0}/{1}",
    "{0} položek":
        "{0} items",
    "systémové funkce pro metadata nejsou dostupné ({0})":
        "system functions for metadata are not available ({0})",
    "ponechaný soubor už neexistuje nebo není dostupný":
        "the kept file no longer exists or is not available",
    "soubor už neexistuje":
        "the file no longer exists",
    "není to obyčejný soubor":
        "not a regular file",
    "ponechaný soubor se od hledání změnil – hledej znovu":
        "the kept file has changed since the search – search again",
    "soubor se od hledání změnil – hledej znovu":
        "the file has changed since the search – search again",
    "je uvnitř balíčku nebo skryté složky – mazat se nesmí":
        "is inside a package or hidden folder – must not be deleted",
    "je to tentýž soubor (stejný disk připojený dvakrát?) – přeskočeno":
        "it is the same file (the same disk mounted twice?) – skipped",
    "obsah se liší od ponechaného souboru (jeden z nich může být poškozený) – přeskočeno":
        "content differs from the kept file (one of them may be damaged) – skipped",
    "liší se resource fork (náhled/ikona starších Mac souborů) – přeskočeno (APFS klon si ho umí ponechat)":
        "resource fork differs (preview/icon of older Mac files) – skipped (an APFS clone can keep it)",
    "soubor nejde přečíst – chybí oprávnění: {0}":
        "the file cannot be read – permission missing: {0}",
    "soubor nejde celý přečíst (může být poškozený): {0} – přeskočeno":
        "the file cannot be read completely (it may be damaged): {0} – skipped",
    "má jiné štítky nebo komentář Finderu – přeskočeno (pevný odkaz by je přepsal; použij APFS klon)":
        "has different Finder tags or comment – skipped (a hard link would overwrite them; use an APFS clone)",
    "Ověřuji shodu s originálem {0}/{1}: {2}":
        "Verifying match with the original {0}/{1}: {2}",
    "chybí ponechaný soubor":
        "the kept file is missing",
    "ponechaná složka už neexistuje":
        "the kept folder no longer exists",
    "složka už neexistuje":
        "the folder no longer exists",
    "složky jsou jedna v druhé – přeskočeno":
        "the folders are inside each other – skipped",
    "složka je uvnitř balíčku nebo skryté složky – mazat se nesmí":
        "the folder is inside a package or hidden folder – must not be deleted",
    "složka neobsahuje přesně tytéž soubory jako ponechaná (např. ":
        "the folder does not contain exactly the same files as the kept one (e.g. ",
    ") – přeskočeno":
        ") – skipped",
    "„{0}“ je v jedné složce odkaz a ve druhé soubor – přeskočeno":
        "“{0}” is a link in one folder and a file in the other – skipped",
    "odkaz „{0}“ míří jinam – přeskočeno":
        "link “{0}” points elsewhere – skipped",
    "je to tatáž složka (stejný disk připojený dvakrát?) – přeskočeno":
        "it is the same folder (the same disk mounted twice?) – skipped",
    "soubor „{0}“ se liší od ponechaného – přeskočeno":
        "file “{0}” differs from the kept one – skipped",
    "soubor „{0}“ má jiný resource fork – přeskočeno":
        "file “{0}” has a different resource fork – skipped",
    "složku nejde přečíst – chybí oprávnění: {0}":
        "the folder cannot be read – permission missing: {0}",
    "složku nejde celou přečíst (může být poškozená): {0} – přeskočeno":
        "the folder cannot be read completely (it may be damaged): {0} – skipped",
    "soubory jsou na různých discích – klon není možný, přeskočeno":
        "the files are on different disks – a clone is not possible, skipped",
    "neznámý typ":
        "unknown type",
    "disk není APFS ({0}) – klon není možný, přeskočeno":
        "the disk is not APFS ({0}) – a clone is not possible, skipped",
    "klonování selhalo":
        "cloning failed",
    " – přeskočeno":
        " – skipped",
    "klon se neshoduje s nahrazovaným souborem – nic se nezměnilo":
        "the clone does not match the replaced file – nothing was changed",
    "štítky nebo komentář Finderu se nepodařilo zachovat – soubor přeskočen":
        "Finder tags or comment could not be preserved – file skipped",
    "resource fork se nepodařilo zachovat – soubor přeskočen, nic se nezměnilo":
        "the resource fork could not be preserved – file skipped, nothing was changed",
    "oprávnění (ACL) se nepodařilo zachovat – přeskočeno, nic se nezměnilo":
        "permissions (ACL) could not be preserved – skipped, nothing was changed",
    "sdílí data":
        "shares data",
    "klon nerozpoznán":
        "clone not recognised",
    "; ACL nešlo ověřit":
        "; ACL could not be verified",
    "nepodařilo se smazat dočasný soubor: {0}":
        "could not delete the temporary file: {0}",
    "soubory jsou na různých discích":
        "the files are on different disks",
    "ponechaný soubor se mezitím změnil – nic se nezměnilo":
        "the kept file has changed in the meantime – nothing was changed",
    "{0} (dočasný odkaz {1})":
        "{0} (temporary link {1})",
    "odkaz se nepodařilo vytvořit – soubor zůstal na místě":
        "the link could not be created – the file stayed in place",
    "ponechaný soubor se mezitím změnil nebo zmizel – soubor zůstal na místě":
        "the kept file has changed or disappeared in the meantime – the file stayed in place",
    " – soubor zůstal na místě":
        " – the file stayed in place",
    "původní soubor je v Koši, odkaz se ale jmenuje „{0}“ ({1})":
        "the original file is in the Trash, but the link is named “{0}” ({1})",
    "původní v Koši":
        "original in Trash",
    "alias Finderu jde vytvořit jen na macOS":
        "a Finder alias can only be created on macOS",
    "alias se nepodařilo vytvořit – originál zůstal na místě: ":
        "the alias could not be created – the original stayed in place: ",
    "cíl už existuje: {0}":
        "the target already exists: {0}",
    "kopie v „{0}“ se neshoduje s originálem – originál zůstal na místě":
        "the copy in “{0}” does not match the original – the original stayed in place",
    "originál nešel do Koše":
        "the original did not go to the Trash",
    "zkopírováno do „{0}“, originál ale zůstal na místě ({1})":
        "copied to “{0}”, but the original stayed in place ({1})",
    "pevným odkazem":
        "a hard link",
    "symbolickým odkazem":
        "a symbolic link",
    "Nahrazuji {0}… {1}/{2}":
        "Replacing with {0}… {1}/{2}",
    "Obsah ověřen":
        "Content verified",
    "Označeno":
        "Marked",
    "Název":
        "Name",
    "Velikost (B)":
        "Size (B)",
    "Změněno":
        "Modified",
    "Vytvořeno":
        "Created",
    "Cesta":
        "Path",
    "velikost + datum změny":
        "size + modification date",
    "jen velikost":
        "size only",
    "obsah (pomalé, jisté)":
        "content (slow, certain)",
    "na stejném místě (stejná struktura složek)":
        "in the same place (same folder structure)",
    "kdekoli (jinak uspořádané složky)":
        "anywhere (folders organised differently)",
    "Oboustranně  A ⇄ B  (obě místa budou mít stejný obsah)":
        "Both ways  A ⇄ B  (both places will have the same content)",
    "Rozdílné verze přeskočit":
        "Skip differing versions",
    "Novější verze vyhraje, starší se uchová jako „… (starší verze …)“":
        "Newer version wins, the older one is kept as “… (older version …)”",
    "Procházím {0}… {1} souborů":
        "Scanning {0}… {1} files",
    "jiná velikost":
        "different size",
    "jiné datum změny":
        "different modification date",
    "na jedné straně složka/odkaz, na druhé soubor":
        "a folder/link on one side, a file on the other",
    "jiný cíl odkazu":
        "different link target",
    "Porovnávám obsah… {0}/{1}":
        "Comparing content… {0}/{1}",
    "jiný obsah":
        "different content",
    "nelze přečíst: {0}":
        "cannot read: {0}",
    "Počítám otisky obsahu… {0}/{1}":
        "Computing content fingerprints… {0}/{1}",
    "kopírování selhalo":
        "copying failed",
    "cíl mezitím vznikl: {0}":
        "the target appeared in the meantime: {0}",
    "{0} (starší verze {1}){2}":
        "{0} (older version {1}){2}",
    "Kopíruji {0}/{1}: {2}":
        "Copying {0}/{1}: {2}",
    "kopie se neshoduje s originálem":
        "the copy does not match the original",
    "starší verze":
        "older version",
    "novější verze":
        "newer version",
    "starší verze na druhou stranu":
        "older version to the other side",
    " – chybí oprávnění zapisovat do cíle nebo číst zdroj (Informace → Sdílení a oprávnění; u chráněných složek Plný přístup k disku)":
        " – no permission to write to the target or read the source (Get Info → Sharing & Permissions; for protected folders Full Disk Access)",
    " – do místa {0} nemáš právo zapisovat":
        " – you have no permission to write to place {0}",
    "stejné":
        "same",
    "liší se":
        "different",
    "jiný typ":
        "different type",
    "Stav":
        "Status",
    "Poznámka":
        "Note",
    "Cesta v A":
        "Path in A",
    "Velikost A":
        "Size A",
    "Změněno A":
        "Modified A",
    "Cesta v B":
        "Path in B",
    "Velikost B":
        "Size B",
    "Změněno B":
        "Modified B",
    "vše (i prázdné)":
        "all (incl. empty)",
    "Přetáhni do okna disk nebo složku (můžeš i víc najednou).":
        "Drop a disk or folder into the window (several at once are fine).",
    "  Porovnání dvou míst  ":
        "  Compare two places  ",
    "⬇  Sem přetáhni disk nebo složku":
        "⬇  Drop a disk or folder here",
    "Vybrat složku…":
        "Choose folder…",
    "Přidat další…":
        "Add another…",
    "⚠ Pomocná složka":
        "⚠ Helper folder",
    "🔓 Odemknout a opravit práva…":
        "🔓 Unlock and fix permissions…",
    "Shoda:":
        "Match:",
    "název":
        "name",
    "velikost":
        "size",
    "datum změny":
        "modification date",
    "datum vytvoření":
        "creation date",
    "ověřit obsah":
        "verify content",
    "Velikost:":
        "Size:",
    "skryté soubory":
        "hidden files",
    "uvnitř balíčků (.app, knihovny)":
        "inside packages (.app, libraries)",
    "Hledat":
        "Search",
    "Vyloučené složky…":
        "Excluded folders…",
    "Vymazat paměť otisků obsahu":
        "Clear the content fingerprint cache",
    "Filtr:":
        "Filter:",
    "Použít":
        "Apply",
    "skrýt už sloučené klony":
        "hide already merged clones",
    "Pohled:":
        "View:",
    "Celé složky":
        "Whole folders",
    "Rozbalit vše":
        "Expand all",
    "Sbalit vše":
        "Collapse all",
    "Smazat":
        "Remove",
    "Velikost":
        "Size",
    "Složka / ušetří":
        "Folder / saves",
    "Náhled":
        "Preview",
    "Automaticky:":
        "Automatically:",
    "Označit":
        "Mark",
    "Další označení ▾":
        "More marking ▾",
    "Označit vše ve složce…":
        "Mark all in folder…",
    "Odznačit vše ve složce…":
        "Unmark all in folder…",
    "Zrušit všechna označení":
        "Clear all marks",
    "Označeno: 0":
        "Marked: 0",
    "Export CSV…":
        "Export CSV…",
    "⚡ Uvolnit místo…":
        "⚡ Free up space…",
    "Nahradit ▾":
        "Replace ▾",
    "APFS klonem (doporučeno – soubor zůstane, místo se uvolní)":
        "With an APFS clone (recommended – the file stays, space is freed)",
    "Pevným odkazem (hard link)":
        "With a hard link",
    "Symbolickým odkazem":
        "With a symbolic link",
    "Přesunout do…":
        "Move to…",
    "Do Koše":
        "Move to Trash",
    "Zobrazit ve Finderu":
        "Show in Finder",
    "Otevřít":
        "Open",
    "Rychlý náhled (Quick Look)":
        "Quick Look",
    "Ponechat tento, ostatní ve skupině označit":
        "Keep this one, mark the others in the group",
    "Označit / odznačit":
        "Mark / unmark",
    "Vyloučit tuto složku z hledání":
        "Exclude this folder from searching",
    "Kopírovat cestu":
        "Copy path",
    "⚠ Po minulém mazání s heslem správce zůstaly soubory v pomocné složce (nic se neztratilo) – tlačítko „Pomocná složka“ ji otevře.":
        "⚠ After the last deletion with the administrator password, files were left in a helper folder (nothing was lost) – the “Helper folder” button opens it.",
    "Přetahování nefunguje – použij „Vybrat složku…“":
        "Drag & drop does not work – use “Choose folder…”",
    "Knihovnu pro přetahování se nepodařilo načíst: {0}":
        "The drag & drop library could not be loaded: {0}",
    "Chyba přetahování: {0}":
        "Drag & drop error: {0}",
    "⬇  Pusť – spustím hledání":
        "⬇  Drop it – the search will start",
    "Přetáhni složku nebo disk (ne soubor).":
        "Drop a folder or disk (not a file).",
    "Počkej, až doběhne hledání nebo akce, pak přetáhni znovu.":
        "Wait until the search or action finishes, then drop again.",
    "Vyber složku nebo disk":
        "Choose a folder or disk",
    "Nejdřív přetáhni složku nebo disk.":
        "First drop a folder or disk.",
    "Vyber aspoň jedno kritérium shody.":
        "Select at least one match criterion.",
    "Hledám shody…":
        "Looking for matches…",
    "Zjišťuji, co už je sloučené APFS klonem…":
        "Checking what is already merged by APFS clones…",
    "Hledám celé duplicitní složky…":
        "Looking for whole duplicate folders…",
    "Zastavit":
        "Stop",
    "zpracování zprávy":
        "message handling",
    "Vnitřní chyba – zapsáno do ~/Library/Logs/DuplicitniSoubory/chyby.log":
        "Internal error – written to ~/Library/Logs/DuplicitniSoubory/chyby.log",
    "Celé složky ({0})":
        "Whole folders ({0})",
    "  •  nepřístupné: {0} (Nastavení → Soukromí → Plný přístup k disku)":
        "  •  inaccessible: {0} (Settings → Privacy → Full Disk Access)",
    "  •  pevné odkazy přeskočeny: {0}":
        "  •  hard links skipped: {0}",
    "  •  vyloučené složky: {0}":
        "  •  excluded folders: {0}",
    "  •  z paměti otisků: {0}":
        "  •  from the fingerprint cache: {0}",
    "  •  celé duplicitní složky: {0} (Pohled → Celé složky)":
        "  •  whole duplicate folders: {0} (View → Whole folders)",
    " (obsah ověřen)":
        " (content verified)",
    " (obsah neověřen)":
        " (content not verified)",
    "  •  už sloučeno klonem: {0} skupin":
        "  •  already merged by clones: {0} groups",
    "Prohledáno {0} souborů za {1:.0f} s – {2} skupin duplicit{3}, lze uvolnit až {4}{5}":
        "Scanned {0} files in {1:.0f} s – {2} duplicate groups{3}, up to {4} can be freed{5}",
    "Chyba: ":
        "Error: ",
    "… a dalších {0} skupin (zúžit filtrem; automatické označení a akce platí pro všechny)":
        "… and {0} more groups (narrow down with the filter; automatic marking and actions apply to all)",
    "({0} skupin už sloučených APFS klonem je skryto)":
        "({0} groups already merged by APFS clones are hidden)",
    "  ✓ obsah":
        "  ✓ content",
    "⧉ už sloučeno APFS klonem – zabírá místo jen jednou":
        "⧉ already merged by an APFS clone – takes up space only once",
    "ušetří {0}{1}":
        "saves {0}{1}",
    "{0} souborů  •  {1}":
        "{0} files  •  {1}",
    "… a dalších {0} souborů této skupiny (automatické označení a akce platí i pro ně)":
        "… and {0} more files in this group (automatic marking and actions apply to them too)",
    "složek":
        "folders",
    "souborů":
        "files",
    "Označeno: {0} {1}, {2}":
        "Marked: {0} {1}, {2}",
    "Soubor je uvnitř balíčku nebo skryté složky (např. knihovna Fotek, .git) – smazáním by se poškodila celá knihovna. Může zůstat jen jako ponechaný.":
        "The file is inside a package or hidden folder (e.g. a Photos library, .git) – deleting it would damage the whole library. It can only be kept.",
    "V každé skupině musí aspoň jeden soubor zůstat.":
        "At least one file must stay in each group.",
    "Ve které složce soubory ponechat?":
        "In which folder should files be kept?",
    "Označeno {0} souborů ({1}).":
        "Marked {0} files ({1}).",
    "Vyber složku":
        "Choose a folder",
    "Odznačeno":
        "Unmarked",
    "{0} {1} souborů ve složce {2}.":
        "{0} {1} files in folder {2}.",
    "ověřen – shodný":
        "verified – identical",
    "neověřen":
        "not verified",
    "{0} shodné složky „{1}“\n\nV každé {2} souborů, {3}\nUšetří: {4}\nObsah: {5}\n\nPřed Košem se každá složka projde znovu a porovná soubor po souboru.":
        "{0} identical folders “{1}”\n\nEach has {2} files, {3}\nSaves: {4}\nContent: {5}\n\nBefore moving to the Trash, each folder is scanned again and compared file by file.",
    "neověřen (zapni „ověřit obsah“)":
        "not verified (turn on “verify content”)",
    "{0} soubory se jménem „{1}“\n\nCelkem: {2}\nUšetří: {3}\nObsah: {4}":
        "{0} files named “{1}”\n\nTotal: {2}\nSaves: {3}\nContent: {4}",
    "Označen k odstranění":
        "Marked for removal",
    "Ponechá se":
        "Will be kept",
    "{0}\n\n{1}\n\nVelikost: {2} ({3} B)\nZměněno: {4}\nVytvořeno: {5}\n\n{6}":
        "{0}\n\n{1}\n\nSize: {2} ({3} B)\nModified: {4}\nCreated: {5}\n\n{6}",
    "…":
        "…",
    "(bez náhledu)":
        "(no preview)",
    "Počkej, až doběhne hledání nebo předchozí akce.":
        "Wait until the search or the previous action finishes.",
    "{0} skupin má označené všechny soubory – ty se přeskočí.":
        "{0} groups have all files marked – they will be skipped.",
    "Nic není označeno. Klikni do sloupce „Smazat“ nebo použij „Označit“ dole.":
        "Nothing is marked. Click in the “Remove” column or use “Mark” below.",
    "\n\n🛡 Před akcí se každý soubor porovná bajt po bajtu s ponechaným originálem. Pokud se liší, originál nejde celý přečíst (např. je poškozený) nebo se od hledání změnil, soubor zůstane beze změny.":
        "\n\n🛡 Before the action, each file is compared byte by byte with the kept original. If it differs, the original cannot be read completely (e.g. it is damaged) or it has changed since the search, the file is left unchanged.",
    "{0}\n\n{1} souborů, {2}.{3}\n\nPokračovat?":
        "{0}\n\n{1} files, {2}.{3}\n\nContinue?",
    "heslo správce nebylo zadáno":
        "the administrator password was not entered",
    "Zjišťuji, proč některé soubory nejdou zpracovat…":
        "Finding out why some files cannot be processed…",
    "Ověřuji a dávám do Koše složku {0}/{1}: {2}":
        "Verifying and moving folder {0}/{1} to the Trash: {2}",
    "chybí ponechaná složka":
        "the kept folder is missing",
    "Přesouvám":
        "Moving",
    "{0}: ověřuji a zpracovávám {1}–{2} z {3}":
        "{0}: verifying and processing {1}–{2} of {3}",
    "Přesunout označené soubory do Koše?\n(jdou vrátit: Koš → pravé tlačítko → Vrátit zpět)":
        "Move the marked files to the Trash?\n(they can be restored: Trash → right-click → Put Back)",
    "Přesun do Koše":
        "Move to Trash",
    "Přesunout {0} označených složek ({1}) celé do Koše?\n\n🛡 Každá složka se těsně před tím projde znovu (i skryté a malé soubory) a každý soubor se porovná bajt po bajtu s ponechanou složkou. Když cokoli nesedí (jiný nebo navíc soubor, poškozený obsah), složka zůstane beze změny.":
        "Move {0} marked folders ({1}) entirely to the Trash?\n\n🛡 Right before that, each folder is scanned again (including hidden and small files) and every file is compared byte by byte with the kept folder. If anything does not match (a different or extra file, damaged content), the folder is left unchanged.",
    "Složky do Koše":
        "Folders to Trash",
    "V pohledu „Celé složky“ jde složky dát do Koše nebo nahradit APFS klony. Pro přesun přepni pohled na „Soubory“.":
        "In the “Whole folders” view, folders can be moved to the Trash or replaced with APFS clones. To move them, switch the view to “Files”.",
    "Kam přesunout označené soubory?":
        "Where should the marked files be moved?",
    "Přesunout označené soubory do „{0}“?\n(struktura podsložek se zachová)":
        "Move the marked files to “{0}”?\n(the subfolder structure is preserved)",
    "Přesun":
        "Move",
    "Po odemčení":
        "After unlocking",
    "soubor":
        "file",
    "Aplikace {0} potřebuje heslo správce, aby mohla přesunout {1} {2}, ke kterým nemáš oprávnění.":
        "{0} needs the administrator password to move {1} {2} you have no permission for.",
    "ponechaný soubor se mezitím změnil nebo zmizel – přeskočeno":
        "the kept file has changed or disappeared in the meantime – skipped",
    "S právy správce":
        "With administrator rights",
    "Celé složky jde nahradit jen APFS klonem (soubory zůstanou na místě, data se uloží jednou). Jiné náhrady jsou v pohledu „Soubory“.":
        "Whole folders can only be replaced with an APFS clone (the files stay in place, the data is stored once). Other replacements are in the “Files” view.",
    "Nahradit označené soubory APFS klonem ponechaného souboru?\n\nSoubory zůstanou na svých místech se stejným jménem, data se ale uloží jen jednou – místo se uvolní. Úprava jednoho souboru druhý nezmění. Funguje jen na disku APFS a ve stejném svazku; datum vytvoření se změní.":
        "Replace the marked files with an APFS clone of the kept file?\n\nThe files stay in place with the same name, but the data is stored only once – space is freed. Editing one file does not change the other. Works only on an APFS disk and within the same volume; the creation date changes.",
    "Nahradit označené soubory pevným odkazem?\n\nOba názvy pak ukazují na STEJNÁ data – úprava jednoho změní i druhý. Jen ve stejném svazku.":
        "Replace the marked files with a hard link?\n\nBoth names then point to the SAME data – editing one changes the other. Only within the same volume.",
    "Nahradit označené soubory aliasem Finderu?\n\nPůvodní soubory se přesunou do Koše a na jejich místě vznikne alias. macOS se poprvé zeptá na povolení ovládat Finder.":
        "Replace the marked files with a Finder alias?\n\nThe original files are moved to the Trash and an alias is created in their place. macOS will ask for permission to control Finder the first time.",
    "Nahradit označené soubory symbolickým odkazem?\n\nPůvodní soubory se přesunou do Koše. Odkaz přestane fungovat, když se ponechaný soubor přesune.":
        "Replace the marked files with a symbolic link?\n\nThe original files are moved to the Trash. The link stops working if the kept file is moved.",
    "\n\nPřed náhradou se obsah porovná bajt po bajtu; rozdílné soubory se přeskočí.":
        "\n\nBefore replacing, the content is compared byte by byte; differing files are skipped.",
    "Náhrada ":
        "Replace with ",
    "{0}: hotovo {1} {2} ({3}), přeskočeno ochranou {4}, chyb {5}. Záznam: ~/Library/Logs/DuplicitniSoubory":
        "{0}: done {1} {2} ({3}), skipped for safety {4}, errors {5}. Log: ~/Library/Logs/DuplicitniSoubory",
    "Není co uvolnit – žádné duplicity na disku APFS, které by ještě nebyly sloučené klonem. (Klony umí jen disk APFS.)":
        "Nothing to free up – no duplicates on an APFS disk that are not already merged by a clone. (Only APFS disks support clones.)",
    "{0} skupin nemá ověřený obsah. Teď je ověřím (přečtou se celé soubory, už známé otisky se vezmou z paměti) a pak ukážu, kolik místa se uvolní.\n\nPokračovat?":
        "{0} groups do not have verified content. I will verify them now (whole files are read, known fingerprints come from the cache) and then show how much space will be freed.\n\nContinue?",
    "uvolnit místo":
        "free up space",
    "Po ověření obsahu nezbyly žádné skutečné duplicity k uvolnění (klon jde vytvořit jen mezi soubory na stejném disku).":
        "After verifying the content, no real duplicates are left to free up (a clone can only be created between files on the same disk).",
    "Uvolnit místo nahrazením {0} souborů v {1} skupinách APFS klonem?\n\nUvolní se až {2}.\n\nVšechny soubory zůstanou na svých místech se svými jmény, štítky i daty; jen jejich obsah se na disku uloží jednou. Na každém disku platí: {3}.\n\n🛡 Každý soubor se těsně před náhradou porovná bajt po bajtu s originálem – rozdílné se přeskočí.":
        "Free up space by replacing {0} files in {1} groups with APFS clones?\n\nUp to {2} will be freed.\n\nAll files stay in place with their names, tags and dates; only their content is stored once on the disk. On each disk: {3}.\n\n🛡 Right before replacing, each file is compared byte by byte with the original – differing ones are skipped.",
    "Uvolnit místo":
        "Free up space",
    "Vyloučit z hledání složku\n„{0}“?\n\n(Seznam jde upravit přes ⚙ → Vyloučené složky.)":
        "Exclude this folder from searching\n“{0}”?\n\n(The list can be edited via ⚙ → Excluded folders.)",
    "Hledat znovu bez této složky?":
        "Search again without this folder?",
    "Vymazat paměť otisků obsahu? Příští hledání s ověřením obsahu bude znovu číst všechny soubory.":
        "Clear the content fingerprint cache? The next search with content verification will read all files again.",
    "Paměť otisků vymazána.":
        "Fingerprint cache cleared.",
    "Uložit přehled":
        "Save report",
    "Uloženo: {0}":
        "Saved: {0}",
    "Právě probíhá hledání, porovnání, oprava práv nebo akce se soubory.\n\nOpravdu ukončit? Zbytek akce se neprovede. Soubory se neztratí, ale může zůstat skrytý dočasný soubor (.dup-tmp-…) a oprava práv může zůstat rozpracovaná (vrátit ji jde tlačítkem „Vrátit opravu“).":
        "A search, comparison, permission fix or file action is running.\n\nReally quit? The rest of the action will not be done. No files will be lost, but a hidden temporary file (.dup-tmp-…) may be left behind and a permission fix may stay unfinished (it can be undone with “Undo fix”).",
    "Odemknout a opravit práva":
        "Unlock and fix permissions",
    "Odemknout a opravit práva ve složce":
        "Unlock and fix permissions in a folder",
    "(vyber složku nebo disk)":
        "(choose a folder or disk)",
    "Vybrat…":
        "Choose…",
    "Odemknout zamčené soubory a složky":
        "Unlock locked files and folders",
    "Převzít vlastnictví – vše bude patřit uživateli „{0}“":
        "Take ownership – everything will belong to user “{0}”",
    "Doplnit mi právo číst a zapisovat (práva ostatních se nemění)":
        "Give me read and write permission (others' permissions are unchanged)",
    "Odstranit pravidla ACL (např. zákaz mazání) – jen pokud víš, že je nepotřebuješ":
        "Remove ACL rules (e.g. deny delete) – only if you know you don't need them",
    "Zavřít":
        "Close",
    "Opravit":
        "Fix",
    "Vrátit poslední opravu…":
        "Undo last fix…",
    "Ve které složce nebo disku opravit práva?":
        "In which folder or disk should permissions be fixed?",
    "Vrátit opravu z {0} ({1} položek)…":
        "Undo fix from {0} ({1} items)…",
    "⛔ Tady opravu práv nelze udělat: {0}.":
        "⛔ Permissions cannot be fixed here: {0}.",
    "kontrola práv":
        "permission check",
    "Chyba: {0}":
        "Error: {0}",
    "Prohledáno {0} položek.":
        "Scanned {0} items.",
    "Disk typu {0}: vlastníci a zámky se tu neukládají (nebo je mění server), oprava nemusí mít účinek.":
        "Disk type {0}: owners and locks are not stored here (or the server changes them), the fix may have no effect.",
    "Disk má zapnuté „Ignorovat vlastnictví“ – vlastník se neřeší, přístup má každý.":
        "The disk has “Ignore ownership” turned on – owners don't matter, everyone has access.",
    "🔒 Zamčené: {0}":
        "🔒 Locked: {0}",
    "   (z toho systémový zámek: {0})":
        "   (of which system lock: {0})",
    "👤 Patří jinému uživateli / systému: {0}":
        "👤 Owned by another user / the system: {0}",
    "✋ Bez mého práva číst a zapisovat: {0}":
        "✋ Without my read and write permission: {0}",
    "🚪 Nepřístupné složky (obsah neznámý): {0}":
        "🚪 Inaccessible folders (contents unknown): {0}",
    "✅ S vybranými volbami tu není co opravit.":
        "✅ Nothing to fix with the selected options.",
    "Opraví se {0} položek":
        "{0} items will be fixed",
    " + obsah {0} nepřístupných složek":
        " + contents of {0} inaccessible folders",
    "Bude potřeba heslo správce.":
        "The administrator password will be needed.",
    "Původní stav se uloží – opravu půjde vrátit tlačítkem vlevo dole.":
        "The original state is saved – the fix can be undone with the button at the bottom left.",
    "Pravidla ACL se odstraní u všeho v této složce; jejich vrácení není možné.":
        "ACL rules will be removed from everything in this folder; this cannot be undone.",
    "okno práv":
        "permissions window",
    "\n\nmacOS se zeptá na heslo správce.":
        "\n\nmacOS will ask for the administrator password.",
    "Opravit práva ve složce\n„{0}“?\n\n{1} položek se odemkne / převezme / dostane práva.{2}\n\nPůvodní stav se uloží pro vrácení.":
        "Fix permissions in folder\n“{0}”?\n\n{1} items will be unlocked / taken over / given permissions.{2}\n\nThe original state is saved for undo.",
    "Aplikace {0} potřebuje heslo správce k opravě práv ve složce „{1}“.":
        "{0} needs the administrator password to fix permissions in folder “{1}”.",
    "Hotovo.":
        "Done.",
    " Nepodařilo se: {0}.":
        " Failed: {0}.",
    "Zrušeno – heslo nebylo zadáno.":
        "Cancelled – the password was not entered.",
    "oprava práv":
        "permission fix",
    "Vrátit vlastníky, práva a zámky ve složce\n„{0}“\ndo stavu před opravou ({1} položek)?":
        "Restore owners, permissions and locks in folder\n“{0}”\nto the state before the fix ({1} items)?",
    "Aplikace {0} potřebuje heslo správce k vrácení práv.":
        "{0} needs the administrator password to restore permissions.",
    "Vráceno {0} položek.":
        "Restored {0} items.",
    "Oprava práv ještě běží. Zavřít okno? Oprava doběhne na pozadí.":
        "The permission fix is still running. Close the window? The fix will finish in the background.",
    "Vyloučené složky":
        "Excluded folders",
    "Tyto složky se při hledání duplicit přeskočí.":
        "These folders are skipped when searching for duplicates.",
    "Cesta (např. /Volumes/Backup disk 2/Horus) = jen ta složka.  Samotný název (např. node_modules) = každá složka tohoto jména.":
        "A path (e.g. /Volumes/Backup disk 2/Horus) = only that folder.  A name only (e.g. node_modules) = every folder with that name.",
    "Přidat složku…":
        "Add folder…",
    "Přidat název":
        "Add name",
    "Hotovo":
        "Done",
    "Kterou složku vyloučit?":
        "Which folder should be excluded?",
    "Seznam vyloučených složek změněn – projeví se při dalším hledání.":
        "The list of excluded folders has changed – it takes effect at the next search.",
    "{0}: {1} {2} se nepodařilo zpracovat":
        "{0}: {1} {2} could not be processed",
    "🔒 Zamčené soubory (Finder → Informace → Zamčeno) můžeš odemknout sám. Složky, které byly zamčené, aplikace po akci zase zamkne.":
        "🔒 You can unlock locked files (Finder → Get Info → Locked) yourself. Folders that were locked will be locked again by the app after the action.",
    "👤 Soubory patří jinému uživateli nebo systému – typicky kopie ze starého Macu, z jiného disku nebo ze zálohy. Po zadání hesla správce je aplikace přesune":
        "👤 The files belong to another user or the system – typically copies from an old Mac, another disk or a backup. After you enter the administrator password, the app will move them",
    " do Koše přes pomocnou složku (Vrátit zpět z Koše je pak vrátí do ní, ne na původní místo).":
        " to the Trash via a helper folder (Put Back from the Trash then returns them there, not to the original place).",
    "👤 Soubory patří jinému uživateli nebo systému. Náhrada s heslem správce není možná – použij u nich „Do Koše“, tam se heslo nabídne.":
        "👤 The files belong to another user or the system. Replacing with the administrator password is not possible – use “Move to Trash” for them, where the password is offered.",
    "👤 Některé soubory nejde přečíst, takže se nedá ověřit shoda s originálem. Použij „Opravit práva ve složce…“ (převezme vlastnictví a doplní práva) a akci zopakuj.":
        "👤 Some files cannot be read, so their match with the original cannot be verified. Use “Fix permissions in folder…” (takes ownership and adds permissions) and repeat the action.",
    "🛡 macOS aplikaci nepustil do chráněného místa. Zapni ji v Nastavení systému → Soukromí a zabezpečení → Plný přístup k disku a aplikaci spusť znovu.":
        "🛡 macOS did not let the app into a protected place. Enable it in System Settings → Privacy & Security → Full Disk Access and start the app again.",
    "🛡 Přeskočené soubory zůstaly beze změny – aplikace je záměrně nezpracovala (důvod je u každého v seznamu). Nic se neztratilo.":
        "🛡 Skipped files were left unchanged – the app intentionally did not process them (the reason is shown for each in the list). Nothing was lost.",
    "⛔ Disk jen pro čtení (např. NTFS z Windows) nebo soubory chráněné systémem – ty aplikace změnit nemůže.":
        "⛔ A read-only disk (e.g. NTFS from Windows) or files protected by the system – the app cannot change them.",
    "\n… a dalších {0}":
        "\n… and {0} more",
    "Zkusit s heslem správce ({0})":
        "Try with the administrator password ({0})",
    "Odemknout a zkusit znovu ({0})":
        "Unlock and try again ({0})",
    "Otevřít Plný přístup k disku":
        "Open Full Disk Access",
    "Kopírovat seznam":
        "Copy list",
    "Opravit práva ve složce…":
        "Fix permissions in folder…",
    "→ chybí v B":
        "→ missing in B",
    "← chybí v A":
        "← missing in A",
    "≠ liší se":
        "≠ different",
    "⚠ jiný typ":
        "⚠ different type",
    "= stejné":
        "= same",
    "Rozdíly (vše kromě stejných)":
        "Differences (all except same)",
    "Jen v A (chybí v B)":
        "Only in A (missing in B)",
    "Jen v B (chybí v A)":
        "Only in B (missing in A)",
    "Liší se":
        "Different",
    "Stejné":
        "Same",
    "Vše":
        "All",
    "Přetáhni dvě místa (složky nebo disky) – do A a do B. Můžeš přetáhnout i obě najednou.":
        "Drop two places (folders or disks) – into A and into B. You can also drop both at once.",
    "⬇  Místo {0}":
        "⬇  Place {0}",
    "Hledat soubor:":
        "Find file:",
    "🔓 Opravit práva…":
        "🔓 Fix permissions…",
    "Zobrazit:":
        "Show:",
    "Zaškrtnout vše zobrazené":
        "Check all shown",
    "Odškrtnout vše zobrazené":
        "Uncheck all shown",
    "Doplnit":
        "Fill in",
    "Zobrazit v A ve Finderu":
        "Show in Finder (A)",
    "Zobrazit v B ve Finderu":
        "Show in Finder (B)",
    "Rychlý náhled A":
        "Quick Look A",
    "Rychlý náhled B":
        "Quick Look B",
    "Zaškrtnout / odškrtnout":
        "Check / uncheck",
    "ověřit kopie bajt po bajtu":
        "verify copies byte by byte",
    "Počkej, až doběhne porovnání nebo kopírování.":
        "Wait until the comparison or copying finishes.",
    "Vyber místo {0}":
        "Choose place {0}",
    "(nevybráno)":
        "(not selected)",
    "Vyber obě místa – A i B.":
        "Choose both places – A and B.",
    "Jedno z míst neexistuje (odpojený disk?).":
        "One of the places does not exist (disconnected disk?).",
    "Místa A a B nesmí být stejná ani jedno uvnitř druhého.":
        "Places A and B must not be the same or one inside the other.",
    "Porovnávám…":
        "Comparing…",
    "porovnání":
        "comparison",
    "Porovnáno za {0:.0f} s.":
        "Compared in {0:.0f} s.",
    "  Nepřístupné položky: {0} (Plný přístup k disku).":
        "  Inaccessible items: {0} (Full Disk Access).",
    "Kopírování hotovo, porovnávám znovu…":
        "Copying done, comparing again…",
    "Doplněno {0} položek.":
        "Filled in {0} items.",
    " Zbývá rozdílů: {0}.":
        " Differences left: {0}.",
    " Obě místa mají nyní stejný obsah (porovnáno bajt po bajtu). ✅":
        " Both places now have the same content (compared byte by byte). ✅",
    " Obě místa mají stejné soubory podle: {0}. Pro jistotu ještě porovnej se shodou „obsah“.":
        " Both places have the same files by: {0}. To be sure, compare again with the “content” match.",
    "  Záznam: ~/Library/Logs/DuplicitniSoubory":
        "  Log: ~/Library/Logs/DuplicitniSoubory",
    "Některé položky se nepodařilo doplnit:\n\n{0}":
        "Some items could not be filled in:\n\n{0}",
    "Jen v A: {0} ({1})   •   Jen v B: {2} ({3})   •   Liší se: {4}   •   Stejné: {5}":
        "Only in A: {0} ({1})   •   Only in B: {2} ({3})   •   Different: {4}   •   Same: {5}",
    "… a dalších {0} položek (Doplnit pracuje se všemi)":
        "… and {0} more items (Fill in works with all of them)",
    "Nic k zobrazení – v tomto pohledu nejsou žádné položky.":
        "Nothing to show – there are no items in this view.",
    "složka: {0} s., {1}":
        "folder: {0} files, {1}",
    "Rozdílné verze se sjednotí jen s volbou „Novější verze vyhraje…“ dole.":
        "Differing versions are only unified with the “Newer version wins…” option below.",
    "Nejdřív porovnej obě místa.":
        "First compare both places.",
    "Místa nebo nastavení se od porovnání změnily – porovnej znovu.":
        "The places or settings have changed since the comparison – compare again.",
    "Není co doplnit (v tomto směru a se zaškrtnutými položkami).":
        "Nothing to fill in (in this direction and with the checked items).",
    "Na místě {0} chybí místo: potřeba {1}, volno {2}.":
        "Not enough space in place {0}: needed {1}, free {2}.",
    "Do B se zkopíruje: {0} položek":
        "To be copied to B: {0} items",
    "Do A se zkopíruje: {0} položek":
        "To be copied to A: {0} items",
    "Rozdílné verze sjednotit: {0} (starší se přejmenuje na „… (starší verze …)“)":
        "Unify differing versions: {0} (the older one is renamed to “… (older version …)”)",
    "Rozdílné verze ponechané beze změny: {0}":
        "Differing versions left unchanged: {0}",
    "Celkem k zápisu: A {0}, B {1}":
        "Total to write: A {0}, B {1}",
    "Doplnit obsah?\n\n{0}\n\nNic se nesmaže ani nepřepíše – soubory se jen přidají.\n\nPokračovat?":
        "Fill in content?\n\n{0}\n\nNothing is deleted or overwritten – files are only added.\n\nContinue?",
    "Uložit porovnání":
        "Save comparison",
    "hlavní":
        "main",
    "vlákno":
        "thread",
    "Aplikace je sestavená se zastaralou knihovnou Tk {0} (systémový Python od Applu) – okno se nemusí správně vykreslit.\n\nNainstaluj Python z python.org a aplikaci sestav znovu.":
        "The app was built with an outdated Tk {0} library (Apple's system Python) – the window may not be drawn correctly.\n\nInstall Python from python.org and build the app again.",
    "Vnitřní chyba: {0}\n\nPodrobnosti jsou v ~/Library/Logs/DuplicitniSoubory/chyby.log":
        "Internal error: {0}\n\nDetails are in ~/Library/Logs/DuplicitniSoubory/chyby.log",
    "Aplikaci se nepodařilo spustit:\n\n":
        "The app could not be started:\n\n",
    "\n\nZáznam: ~/Library/Logs/DuplicitniSoubory/chyby.log":
        "\n\nLog: ~/Library/Logs/DuplicitniSoubory/chyby.log",
    "APFS klonem":
        "an APFS clone",
    "aliasem Finderu":
        "a Finder alias",
    "Skupina":
        "Group",
    "ano":
        "yes",
    "ne":
        "no",
    "Jen doplnit B  (A → B)":
        "Fill in B only  (A → B)",
    "Jen doplnit A  (B → A)":
        "Fill in A only  (B → A)",
    "jen v A":
        "only in A",
    "jen v B":
        "only in B",
    "Soubory":
        "Files",
    "Aliasem Finderu":
        "With a Finder alias",
    "Nahrazuji":
        "Replacing",
    "soubory":
        "files",
    "Odebrat":
        "Remove",
    "Porovnat":
        "Compare",
    "odkaz":
        "link",
    "od 1 B":
        "from 1 B",
    "od 10 kB":
        "from 10 kB",
    "od 100 kB":
        "from 100 kB",
    "od 1 MB":
        "from 1 MB",
    "od 10 MB":
        "from 10 MB",
    "od 100 MB":
        "from 100 MB",
    "Pro změnu jazyka je potřeba aplikaci spustit znovu. Restartovat teď?":
        "The app needs to restart to change the language. Restart now?",
    "Aktualizace":
        "Update",
    "Stahuji {0}…":
        "Downloading {0}…",
    "stažený soubor nemá očekávanou velikost":
        "the downloaded file does not have the expected size",
    "Zkontrolovat aktualizace…":
        "Check for updates…",
    "Kontrolovat aktualizace při spuštění":
        "Check for updates at startup",
    "Jazyk se změní po příštím spuštění aplikace.":
        "The language will change the next time the app starts.",
    "⬆ Nová verze {0} – stáhnout":
        "⬆ New version {0} – download",
    "(bez popisu změn)":
        "(no release notes)",
    "stahování selhalo":
        "download failed",
    "Nepodařilo se spojit s GitHubem. Zkontroluj připojení k internetu.":
        "Could not connect to GitHub. Check your internet connection.",
    "Máš nejnovější verzi ({0}).":
        "You have the latest version ({0}).",
    "Stáhnout a otevřít":
        "Download and open",
    "Staženo do {0}. Otevřel se instalační disk – zavři tuto aplikaci a přetáhni novou verzi do složky Aplikace (nahradit).":
        "Downloaded to {0}. The installer disk has opened – quit this app and drag the new version to the Applications folder (replace).",
    "Stažení se nepodařilo: {0}":
        "Download failed: {0}",
    "Je k dispozici nová verze {0}":
        "A new version {0} is available",
    "Máš verzi {0}.":
        "You have version {0}.",
    "Později":
        "Later",
    "Otevřít stránku vydání":
        "Open release page",
    "Tuto verzi přeskočit":
        "Skip this version",
    "Nainstalovat a restartovat":
        "Install and restart",
    "Právě něco běží. Přerušit to a nainstalovat novou verzi?":
        "Something is running. Stop it and install the new version?",
    "je ve složce synchronizované s cloudem (OneDrive, Google Drive, iCloud…) – náhrada by soubor znovu nahrála do cloudu a mohla smazat jeho historii verzí a sdílení; přeskočeno (použij Do Koše)":
        "is in a folder synced with the cloud (OneDrive, Google Drive, iCloud…) – replacing it would upload the file again and could remove its version history and sharing; skipped (use Move to Trash)",
    "soubor je jen v cloudu (není stažený) – ověření shody by ho celý stáhlo; přeskočeno (stáhni ho ve Finderu: pravé tlačítko → Stáhnout nyní)":
        "the file is only in the cloud (not downloaded) – verifying the match would download all of it; skipped (download it in Finder: right-click → Download Now)",
    "\n\n☁ {0} souborů je ve složce synchronizované s cloudem (OneDrive, Google Drive, iCloud…). Smazáním nebo přesunem zmizí i z cloudu a ze všech zařízení – u sdílených složek i ostatním lidem. Cloud je obvykle ještě nějakou dobu drží ve svém koši na webu.":
        "\n\n☁ {0} files are in a folder synced with the cloud (OneDrive, Google Drive, iCloud…). Deleting or moving them removes them from the cloud and all devices too – in shared folders also for other people. The cloud usually keeps them in its web recycle bin for a while.",
    "soubor „{0}“ je jen v cloudu (není stažený) – ověření by ho celý stáhlo; přeskočeno":
        "file “{0}” is only in the cloud (not downloaded) – verifying would download all of it; skipped",
    "  •  jen v cloudu (nestaženo, neověřeno): {0}":
        "  •  only in the cloud (not downloaded, not verified): {0}",
    "☁ Vybraná složka se synchronizuje s cloudem ({0}).\n\n• Smazání nebo přesun souboru se projeví i v cloudu a na všech ostatních zařízeních (u sdílených složek i ostatním lidem).\n• APFS klony, pevné odkazy, aliasy ani symlinky se tu dělat nebudou – cloud by soubory nahrál znovu a mohl by smazat jejich historii verzí.\n• Soubory jen v cloudu (nestažené) se kvůli porovnání nestahují.":
        "☁ The selected folder is synced with the cloud ({0}).\n\n• Deleting or moving a file also affects the cloud and all other devices (in shared folders also other people).\n• APFS clones, hard links, aliases and symlinks will not be made here – the cloud would upload the files again and could remove their version history.\n• Files that are only in the cloud (not downloaded) are not downloaded for comparison.",
    "instalační skript se nepodařilo stáhnout":
        "the installer script could not be downloaded",
    "stažený soubor je poškozený":
        "the downloaded file is damaged",
    "⬆ Nová verze {0} – nainstalovat":
        "⬆ New version {0} – install",
    "Je k dispozici nová verze {0}, ale bez instalačního souboru. Otevřu stránku vydání.":
        "A new version {0} is available, but without an installer file. Opening the release page.",
    "Je k dispozici nová verze {0} (máš {1}).\n\n{2}\n\nNainstalovat ji teď? Aplikace se sama aktualizuje a spustí znovu.":
        "A new version {0} is available (you have {1}).\n\n{2}\n\nInstall it now? The app will update itself and restart.",
    "Stahuji novou verzi {0}… Pak se aplikace zavře, aktualizuje a spustí znovu.":
        "Downloading the new version {0}… Then the app will close, update and restart.",
    "Instaluji – aplikace se za chvíli spustí znovu…":
        "Installing – the app will restart in a moment…",
    "Aktualizaci se nepodařilo stáhnout: {0}\n\nAplikace běží dál beze změny. Zkus to později.":
        "The update could not be downloaded: {0}\n\nThe app keeps running unchanged. Try again later.",
    "Zkontrolovat aktualizace":
        "Check for updates",
    "verze {0}":
        "version {0}",
    "Co je nového":
        "What's new",
    "Skrýt":
        "Hide",
    "✓  Aplikace byla aktualizována na verzi {0}":
        "✓  The app was updated to version {0}",
    "Novinky ve verzi {0}:\n\n{1}":
        "What's new in version {0}:\n\n{1}",
    "🔔  Je k dispozici nová verze {0}  (máš {1})":
        "🔔  A new version {0} is available  (you have {1})",
    "je ve složce synchronizované s cloudem ({0}) – soubory v cloudu se nikdy neoznačují ani nemažou; přeskočeno":
        "is in a folder synced with the cloud ({0}) – files in the cloud are never marked or deleted; skipped",
    "složka je (nebo obsahuje) data synchronizovaná s cloudem ({0}) – nesmí se mazat; přeskočeno":
        "the folder is (or contains) data synced with the cloud ({0}) – it must not be deleted; skipped",
    "☁ Soubor je ve složce synchronizované s cloudem – takové soubory aplikace nikdy neoznačí ani nesmaže. Může zůstat jen jako ponechaný originál.":
        "☁ The file is in a folder synced with the cloud – the app never marks or deletes such files. It can only be kept as the original.",
    "… a dalších {0}":
        "… and {0} more",
    "☁ Ve vybraných složkách jsou data synchronizovaná s cloudem:\n\n{0}\n\nSoubory v nich se v seznamu zobrazí (☁), ale aplikace je nikdy neoznačí, nesmaže, nepřesune ani nenahradí – smazání by se projevilo v cloudu i na ostatních zařízeních. Mohou ale sloužit jako ponechaný originál: smazat jde jen jejich kopie mimo cloud.":
        "☁ The selected folders contain data synced with the cloud:\n\n{0}\n\nFiles in them are shown in the list (☁), but the app never marks, deletes, moves or replaces them – deleting would affect the cloud and other devices. They can still serve as the kept original: only their copies outside the cloud can be deleted.",
    "  •  ☁ v cloudu (chráněno): {0}":
        "  •  ☁ in the cloud (protected): {0}",
}
