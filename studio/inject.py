"""Inject separate Studio controls without deleting or replacing UltraBox."""
from pathlib import Path
import shutil,sys,re
upstream,source=map(Path,sys.argv[1:3])
target=upstream/"editor"/"main.ts"
s=target.read_text()
a='import {SongEditor} from "./SongEditor";'
b='editor.whenUpdated();'
assert s.count(a)==1 and s.count(b)==1, "Upstream integration anchors changed"
s=s.replace(a,a+'\nimport { mountStudio } from "./StudioBridge";')
s=s.replace(b,b+'\nmountStudio(doc,editor);')
target.write_text(s)
shutil.copyfile(source/"StudioBridge.ts",upstream/"editor"/"StudioBridge.ts")
shutil.copyfile(source/"studio.css",upstream/"website"/"studio.css")
p=upstream/"website"/"index.html"
s=p.read_text()
assert s.count("</head>")==1
s=s.replace("</head>",'<link rel="stylesheet" href="/studio.css" />\n</head>')
s=s.replace("<title>UltraBox</title>","<title>Studio</title>")
p.write_text(s)
