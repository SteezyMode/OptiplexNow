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
# Upstream's pinned source compiles with older jQuery typings but newer @types
# treats .get(0) as possibly undefined. Assert the existing DOM contract; this
# does not change runtime behavior.
editor_file=upstream/"editor"/"SongEditor.ts"
editor_source=editor_file.read_text()
for prefix in ("modInstrumentText","modChannelText","modSettingText","modFilterText"):
    old='$("#'+prefix+'" + mod).get(0)'
    new=old+"!"
    editor_source=editor_source.replace(old,new)
editor_file.write_text(editor_source)

shutil.copyfile(source/"StudioBridge.ts",upstream/"editor"/"StudioBridge.ts")
shutil.copyfile(source/"studio.css",upstream/"website"/"studio.css")
p=upstream/"website"/"index.html"
s=p.read_text()
assert s.count("</head>")==1
s=s.replace("</head>",'<link rel="stylesheet" href="/studio.css" />\n</head>')
s=s.replace("<title>UltraBox</title>","<title>Studio</title>")
p.write_text(s)
