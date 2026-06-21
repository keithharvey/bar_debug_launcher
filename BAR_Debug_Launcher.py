import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter.messagebox import showinfo
#from ttkthemes import ThemedTk
from calendar import month_name

import platform
import os
import re
import subprocess
import shlex
import sys
import shutil
import webbrowser
import requests
try:
    import py7zr
except ImportError:
    print ("Cant find py7zr lib, no engine downloads available")
    py7zr = None


from parse_demo_file import Parse_demo_file

from slpp import slpp

from bar_launch.core import Context, find_linux_launcher_binary as _find_linux_launcher_binary, host_cmd_prefix
from bar_launch.engine_cmd import build_runcmd
from bar_launch.intents import (
    BOOT_CHOICES,
    Intent,
    PLAY_CHOICES,
    default_boot,
    resolve_intent,
)

#Try to figure out the BAR install path:
barinstallpath = os.environ.get("BAR_INSTALL_PATH") or os.path.abspath(os.path.dirname(sys.argv[0])) 
cwd = os.getcwd()
#This is needed for double-click launches, as then the CWD is wherever the demo file is
os.chdir(barinstallpath)
print("Exe path", barinstallpath, "cwd", cwd)
print("Setting path to", barinstallpath)

def exitpause(message = ""):
    print("Terminating: ", message)
    if platform.system() == 'Windows':
        os.system("pause")
    exit(1)

#DEBUGGINGS
if False:
    #sys.argv.append("C:/Users/Peti/AppData/Local/Programs/Beyond-All-Reason/2025-01-18_17-59-17-091_Supreme Isthmus Winter v1.8_2025.01.3.sdfz")
    #sys.argv.append("C:/Users/Peti/AppData/Local/Programs/Beyond-All-Reason/2025-04-15_17-01-59-622_DWorld_V4_2025.01.6.sdfz")
    sys.argv.append("C:/Users/Peti/AppData/Local/Programs/Beyond-All-Reason/2025-04-16_07-46-16-355_All That Glitters v2_2025.03.9.sdfz")
    #sys.argv.append("C:/Users/Peti/AppData/Local/Programs/Beyond-All-Reason/2025-04-26_20-49-19-461_All That Glitters v2_2025.04.01.sdfz")
    barinstallpath = "C:/Users/Peti/AppData/Local/Programs/Beyond-All-Reason"
    os.chdir(barinstallpath)

#maps = ['Ill choose my own once ingame']

def find_linux_datadir():
    # Searches for the BAR install directory in the ~same was as launcher
    # and returns absolute path
    try:
        documents = subprocess.check_output(
            ['xdg-user-dir', 'DOCUMENTS'], encoding='utf-8').strip()
    except:
        documents = os.path.expanduser("~")  # Yep, that's fallback
    if os.path.exists(os.path.join(documents, 'Beyond All Reason')):
        return os.path.join(documents, 'Beyond All Reason')

    state_home = os.getenv('XDG_STATE_HOME',
        default=os.path.join(os.path.expanduser("~"), '.local', 'state'))
    return os.path.join(state_home, 'Beyond All Reason')

def find_linux_launcher_binary():
    # Honors $BAR_APPIMAGE_PATH and --launcher-binary first; falls back to
    # the legacy cwd scan so the standalone "drop next to the AppImage and
    # double-click" workflow keeps working.
    return _find_linux_launcher_binary(barinstallpath)

if platform.system() == 'Windows':
    engine_binary = 'spring.exe'
    prd_binary = 'pr-downloader.exe'
    datafolder = os.environ.get("BAR_DATA_DIR", 'data')
    launcher_binary_display = launcher_binary = 'Beyond-All-Reason.exe'
    engine_download_baseurl = 'https://github.com/beyond-all-reason/spring/releases/download/spring_bar_%7BBAR105%7D{enginebaseversion}/spring_bar_.BAR105.{enginebaseversion}_windows-64-minimal-portable.7z'
    engine_download_baseurl_new = 'https://github.com/beyond-all-reason/spring/releases/download/{enginebaseversion}/spring_bar_.{releaseID}.{enginebaseversion}_windows-64-minimal-portable.7z'
    engine_download_baseurl_newest = 'https://github.com/beyond-all-reason/RecoilEngine/releases/download/{enginebaseversion}/recoil_{enginebaseversion}_amd64-windows.7z'
elif platform.system() == 'Linux':
    engine_binary = 'spring'
    prd_binary = 'pr-downloader'
    # Later we depend on that os.join(barinstallpath, datafolder) returns
    # datafolder when datafolder is absolute path.
    datafolder = find_linux_datadir()
    launcher_binary = find_linux_launcher_binary()
    launcher_binary_display= "Beyond-All-Reason AppImage"
    engine_download_baseurl = 'https://github.com/beyond-all-reason/spring/releases/download/spring_bar_%7BBAR105%7D{enginebaseversion}/spring_bar_.BAR105.{enginebaseversion}_linux-64-minimal-portable.7z'
    engine_download_baseurl_new = 'https://github.com/beyond-all-reason/spring/releases/download/{enginebaseversion}/spring_bar_.{releaseID}.{enginebaseversion}_linux-64-minimal-portable.7z'
    engine_download_baseurl_newest = 'https://github.com/beyond-all-reason/RecoilEngine/releases/download/{enginebaseversion}/recoil_{enginebaseversion}_amd64-linux.7z'
else:
    raise Exception('Unsupported platform')


archivecache = {} # maps gamename/mapname to filename
maps = {}
games = {}
menus = {}
engines = {}
modinfos = {}

scriptbase = """
[game]
{
    [allyteam1]
    {
        numallies=0;
    }
    [team1]
    {
        teamleader=0;
        allyteam=1;
    }
    [ai0]
    {
        shortname=NullAI;
        name=NullAI;
        version=0.1;
        team=1;
        host=0;
    }
    [modoptions]
    {
        %s
    }
    [allyteam0]
    {
        numallies=0;
    }
    [team0]
    {
        teamleader=0;
        allyteam=0;
    }
    [player0]
    {
        team=0;
        name=DebugLauncher;
    }
    mapname=%s;
    myplayername=DebugLauncher;
    ishost=1;
    gametype=%s;
    nohelperais=0;
}"""

# returns a dict of engineversion:absolutespringexepath
def findengines(enginefolder):
    engines = {}
    enginedirs  = {}
    if os.path.exists(enginefolder):
        for engineversion in os.listdir(enginefolder):
            enginedir = os.path.join(enginefolder, engineversion)
            if os.path.isdir(enginedir) and os.path.exists(os.path.join(enginedir, engine_binary)):
                enginepath = os.path.join(enginedir, engine_binary)
                print(f"Found engine version {engineversion} in path: {enginepath}")
                engines[engineversion] = enginepath
    if len(engines) == 0:
        engines["NO ENGINES FOUND!"] = "NO ENGINES FOUND!"
    return engines,enginedirs

# returns three dicts from archivecach
def parsecache(path):
    global archivecache           
    maps = {} # key archive name to value filename
    games = {}
    menus = {}
    try:
        cachefiles = []
        for item in os.listdir(path):
            itempath = os.path.join(path, item)
            if os.path.isdir(itempath):
                for archivecachefile in os.listdir(itempath):
                    if 'archivecache' in archivecachefile.lower() and archivecachefile.lower().endswith('.lua'):
                        archivecachefilepath = os.path.join(itempath, archivecachefile)
                        lastmodified = os.path.getmtime(archivecachefilepath)
                        print ("Found a cache file", item, archivecachefile, "last modified:", lastmodified)
                        cachefiles.append((archivecachefilepath, lastmodified))
            elif 'archivecache' in item.lower() and item.lower().endswith('.lua'):
                lastmodified = os.path.getmtime(itempath)
                print ("Found a cache file (direct)", item, "last modified:", lastmodified)
                cachefiles.append((itempath, lastmodified))

        if len(cachefiles) > 0:
            cachefiles = sorted(cachefiles, key = lambda x: x[1], reverse = True)
            archivecachefilepath = cachefiles[0][0]
            print ("Loading Archive Cache File:", archivecachefilepath)
            archivecachecontents = open(archivecachefilepath).read()
            archivetable = '{' + archivecachecontents.partition('{')[2].rpartition('}')[0] +  '}'
            archivetable = slpp.decode(archivetable)
            for archive in archivetable['archives']:
                if 'archivedata' in archive and 'modtype' in archive['archivedata']:
                    archivedata = archive['archivedata']
                    modtype = archivedata['modtype']
                    if modtype == 3: # map
                        maps[archivedata['name']] = archive['name']
                    elif modtype == 5: #menu
                        menus[archivedata['name']] = archive['name']
                    elif modtype == 1: #game
                        games[archivedata['name']] = archive['name']
            print (f"Found {len(maps)} maps, {len(games)} games, {len(menus)} menus")
    except Exception as e:
        print ("parsecache error, dont code blind!", e)
    return maps, games, menus

def parsemodinfo(path):
    try:
        with open(path, 'r') as f:
            contents = f.read()
        table_str = '{' + contents.partition('{')[2].rpartition('}')[0] + '}'
        return slpp.decode(table_str)
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        return None

def refresh():
    global modinfos
    #global enginepaths
    #global enginedirs
    global maps, games, menus, engines, enginedirs
    maps, games, menus = parsecache(os.path.join(barinstallpath, datafolder, "cache"))
    engines, enginedirs = findengines(os.path.join(barinstallpath, datafolder, "engine"))

    #parsemaps()
    # check for bar.sdd
    
    modinfos['Spring-launcher with rapid://byar-chobby:test'] = {'modtype': '0', 'name': 'rapid://byar-chobby:test'}
    modinfos['Latest BYAR Chobby Lobby: rapid://byar-chobby:test'] = {'name': 'rapid://byar-chobby:test', 'version': '', 'modtype': '5'}
    modinfos['Latest BAR Game: rapid://byar:test'] = {'name': 'rapid://byar:test', 'version': '', 'modtype': '1'}
    for menuname in menus.keys():
        if '$VERSION' in menuname:
            modinfos[f'Spring-launcher with {menuname}'] = {'modtype': '0', 'name': menuname}
            modinfos[f'{menuname} (no launcher)'] = {'modtype': '5', 'name': menuname}
    for gamename in games.keys():
        if '$VERSION' in gamename:
            modinfos[gamename] = {'modtype': '1', 'name': gamename}

    # Surface locally-checked-out games (anything symlinked or hardlinked
    # into <data-dir>/games/) as [LOCAL] entries so the dropdown
    # distinguishes them from rapid:// builds.
    gamespath = os.path.join(datafolder, 'games')
    if os.path.exists(gamespath):
        for gamedir in os.listdir(gamespath):
            gamepath = os.path.join(gamespath, gamedir)
            if not os.path.isdir(gamepath):
                continue
            modinfopath = os.path.join(gamepath, 'modinfo.lua')
            if not os.path.exists(modinfopath):
                continue
            modinfo = parsemodinfo(modinfopath)
            if not (modinfo and 'name' in modinfo):
                continue
            base_name = modinfo['name']
            version = modinfo.get('version', '')
            if version == '$VERSION' and '$VERSION' not in base_name:
                name = f"{base_name} $VERSION"
            else:
                name = base_name
            mtype = str(modinfo.get('modtype', '1'))
            display_name = f"[LOCAL] {gamedir}"
            modinfos[display_name] = {'modtype': mtype, 'name': name}
            if mtype == '5':
                modinfos[f"[LOCAL] Spring-launcher with {gamedir}"] = {'modtype': '0', 'name': name}

    for k, v in modinfos.items():
        print(k, v)

refresh()

# Gather cmd args:
# https://github.com/beyond-all-reason/spring-launcher/blob/887937649014318d0da9e6e4b67f831366ce392b/src/engine_launcher.js#L149

# isolation = true
# C:\Users\Peti\AppData\Local\Programs\Beyond-All-Reason\data\engine\105.1.1-1177-gada72b4 bar\spring.exe \n
# --write-dir C:\Users\Peti\AppData\Local\Programs\Beyond-All-Reason\data --isolation --menu BYAR Chobby $VERSION

def try_start_replay(replayfilepath):
    if not replayfilepath.lower().endswith('.sdfz'):
        print ("Replay file path does not end with .sdfz", replayfilepath)
        exitpause("")
    if not os.path.exists(replayfilepath):
        print ("Path to replay file incorrect", replayfilepath)
        exitpause("")
    
    #1. Try to copy replay into demos folder
    #always assume that barpath is 
    replayfiledir, replayfilename = os.path.split(replayfilepath)
    savedreplaypath = os.path.join(barinstallpath, datafolder,'demos', replayfilename)
    print (replayfilepath,savedreplaypath)
    if not os.path.exists(savedreplaypath):
        shutil.copy2(replayfilepath,savedreplaypath)
    
    #2. Parse demo file
    demo = Parse_demo_file(savedreplaypath)
    demo.parse_header_and_script()

    engineversion = demo.header['versionString'] # 105.1.1-1354-g72b2d55 BAR105
    mapname = demo.script.other['mapname'] # Archsimkats_Valley_V1
    modname = demo.script.other['modname'] # Beyond All Reason test-21960-4e943b5
    print (f"Replay info: Engine={engineversion}, Map={mapname}, Game={modname}")

    #3. Check engine version and download if needed, compare
    if engineversion.startswith('2') and engineversion.count('.') == 2: 
        print("New engine version format found", engineversion)
        subversions = engineversion.split('.') # e.g. 2025.01.3
        releaseID = f'rel{subversions[0][2:]}{subversions[1]}'
        enginedir = f'{releaseID}.{engineversion}' # e.g. rel2501.2025.01.3

        if enginedir in engines or any(engineversion in x for x in engines.keys()):
            if enginedir in engines:
                print ("Found exact correct engine at", enginedir)
            else:
                # try to find the engine version in the engines dict
                for engineversionkey in engines.keys():
                    if engineversion in engineversionkey:
                        enginedir = engineversionkey
                        break
                print ("Found hopefully correct engine at", enginedir)
        else:
            print ("Engine ",os.path.join(enginedir,engine_binary) ,"not found in known engines")

            #print (str(engines))
            print ("Attempting to download engine from github")
            if engineversion.startswith('2025.01'):

                baseurl = engine_download_baseurl_new.format(releaseID=releaseID, enginebaseversion = engineversion)
                archivename = f'engine.{engineversion}.7z'
                print(baseurl)
            else:
                baseurl = engine_download_baseurl_newest.format( enginebaseversion = engineversion)
                archivename = baseurl.split('/')[-1]
                enginedir = f'recoil_{engineversion}' # e.g. rel2501.2025.01.3
            try:
                print("Downloading engine from", baseurl)
                print("Saving as", archivename)
                with open(archivename,'wb') as enginearchive: # yeah this doesnt 404
                    enginearchive.write(requests.get(baseurl).content)
            except Exception as e:
                print ("Unable to download engine from", baseurl, e)
                exitpause("")

            try:
                newenginedir = os.path.join(barinstallpath, datafolder, 'engine' , enginedir)
                if not os.path.exists(newenginedir):
                    os.makedirs(newenginedir)
                if platform.system() == 'Windows':
                    programfiles = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
                    programfiles = os.path.join(programfiles, '7-Zip', "7z.exe")
                    if os.path.exists(programfiles):
                        un7zipcmd = f'"{programfiles}" x -y -o{newenginedir} {archivename}'
                        print(un7zipcmd)
                        retval = os.system(un7zipcmd)
                        if retval != 0:
                            print ("ERROR: 7z.exe failed to extract engine archive", archivename, "with return code", retval, "using command", un7zipcmd)
                            exitpause("")
                    else:
                        print(f"ERROR: 7z.exe not found in {programfiles} please install 7zip to C:\\Program Files\\7-Zip\\7z.exe")
                        exitpause("")
                else:
                    with py7zr.SevenZipFile(archivename,'r') as archive:
                        archive.extractall(path = newenginedir)
            except Exception as e:
                print ("Failed to extract engine archive", archivename, e)
                raise e
                exitpause("")
    else:
        
        # 105.1.1-1354-g72b2d55 BAR105 to 105.1.1-941-g941148f bar
        enginebaseversion = engineversion.partition(' ')[0] 
        enginedir = os.path.join(enginebaseversion + ' bar')
        if enginedir in engines:
            print ("Found correct engine at", enginedir)
        else:
            print ("Engine ",os.path.join(enginedir,engine_binary) ,"not found in known engines")
            print (str(engines))
            print ("Attempting to download engine from github")
            baseurl = engine_download_baseurl.format(enginebaseversion=enginebaseversion)
            archivename = f'engine.{enginebaseversion}.7z'
            print(baseurl)
            try:
                with open(archivename,'wb') as enginearchive:
                    enginearchive.write(requests.get(baseurl).content)
            except Exception as e:
                print ("Unable to download engine from", baseurl, e)
                exitpause("")  

            try:
                newenginedir = os.path.join(barinstallpath, datafolder, 'engine' , enginedir)
                if not os.path.exists(newenginedir):
                    os.makedirs(newenginedir)
                if platform.system() == 'Windows':
                    programfiles = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
                    programfiles = os.path.join(programfiles, '7-Zip', "7z.exe")
                    if os.path.exists(programfiles):
                        un7zipcmd = f'"{programfiles}" x -y -o{newenginedir} {archivename}'
                        print(un7zipcmd)
                        retval = os.system(un7zipcmd)
                        if retval != 0:
                            print ("ERROR: 7z.exe failed to extract engine archive", archivename, "with return code", retval, "using command", un7zipcmd)
                            exitpause("")
                    else:
                        print(f"ERROR: 7z.exe not found in {programfiles} please install 7zip to C:\\Program Files\\7-Zip\\7z.exe")
                        exitpause("")
                else:
                    with py7zr.SevenZipFile(archivename,'r') as archive:
                        archive.extractall(path = newenginedir)
            except Exception as e:
                print ("Failed to extract engine archive", archivename, e)
                exitpause("")

    #4.1 Get game and map

    my_env = os.environ.copy()
    my_env['PRD_RAPID_USE_STREAMER'] = 'false'
    my_env['PRD_RAPID_REPO_MASTER'] = 'https://repos-cdn.beyondallreason.dev/repos.gz'
    my_env['PRD_HTTP_SEARCH_URL'] = 'https://files-cdn.beyondallreason.dev/find'

    print("Environment:")
    for k,v in my_env.items():
        print (k,v)

    prdcmds = []
    if modname not in games:
        prdcmds.append( f'"{os.path.join(barinstallpath, datafolder, "engine", enginedir, prd_binary)}" --filesystem-writepath "{os.path.join(barinstallpath, datafolder)}" --download-game "{modname}"')
    else:
        print (f"Found {modname} in archive cache")
    if mapname not in maps:
        prdcmds.append( f'"{os.path.join(barinstallpath, datafolder, "engine", enginedir, prd_binary)}" --filesystem-writepath "{os.path.join(barinstallpath, datafolder)}" --download-map "{mapname}"' )
    else:
        print (f"Found {mapname} in archive cache")

    for prdcmd in prdcmds:
        print (f"Running pr-downloader command: {prdcmd}")
        prdsuccess = subprocess.call(prdcmd, shell= True, env = my_env)
        if prdsuccess==0:
            print("PRD success")
        else:
            print ("PRD failed")
            exitpause("")

    #5. start the demo 
    runcmd = f'"{os.path.join(barinstallpath, datafolder,"engine",enginedir, engine_binary)}"  --isolation --write-dir "{os.path.join(barinstallpath, datafolder)}" "{savedreplaypath}"'
    print ("Launching engine for replay with:", runcmd)
    subprocess.Popen(host_cmd_prefix() + shlex.split(runcmd),close_fds=True )
    #print (demo.header)


class _Tooltip:
    """Lightweight hover/focus tooltip. text_func is called at show-time so
    each tooltip reflects the current selection rather than a stale snapshot."""
    def __init__(self, widget, text_func, delay_ms=350):
        self.widget = widget
        self.text_func = text_func
        self.delay_ms = delay_ms
        self.tip = None
        self.after_id = None
        widget.bind('<Enter>', self._schedule, add='+')
        widget.bind('<FocusIn>', self._schedule, add='+')
        widget.bind('<Leave>', self._hide, add='+')
        widget.bind('<FocusOut>', self._hide, add='+')
        widget.bind('<ButtonPress>', self._hide, add='+')

    def _schedule(self, _evt=None):
        self._cancel()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self.after_id:
            try: self.widget.after_cancel(self.after_id)
            except Exception: pass
            self.after_id = None

    def _show(self):
        text = self.text_func() or ""
        if not text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(self.tip, background='#1f2937', borderwidth=0)
        frame.pack()
        tk.Label(frame, text=text, background='#1f2937', foreground='#f9fafb',
                 justify=tk.LEFT, padx=10, pady=8,
                 font=('TkDefaultFont', 9), wraplength=420).pack()

    def _hide(self, _evt=None):
        self._cancel()
        if self.tip:
            try: self.tip.destroy()
            except Exception: pass
            self.tip = None


if len(sys.argv) < 2: # no arguments passed, use GUI
    root = tk.Tk()
    # Defer to the OS: a healthy desktop Tk already honors the fontconfig default
    # family and the display DPI (tk scaling), so we leave those alone on KDE /
    # GNOME / etc. But some Tk builds (notably Homebrew's on Linux) can't see the
    # system fonts and fall back to the non-scalable X11 'fixed' bitmap -- detect
    # that and pin to the best available scalable family so text renders & scales.
    # BAR_TK_SCALING=<float> overrides the DPI-derived scaling for manual tuning.
    import tkinter.font as _tkfont
    _avail = {f.lower(): f for f in _tkfont.families(root)}
    def _pick_family(prefs, fallback):
        for _p in prefs:
            if _p.lower() in _avail:
                return _avail[_p.lower()]
        return fallback
    _default = _tkfont.nametofont('TkDefaultFont')
    if _default.actual('family').lower() == 'fixed':
        UI_SANS = _pick_family(['DejaVu Sans', 'Noto Sans', 'Liberation Sans', 'Helvetica', 'Arial'], 'Liberation Sans')
        UI_MONO = _pick_family(['DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono', 'Courier New'], 'Liberation Mono')
        for _name in _tkfont.names(root):
            _tkfont.nametofont(_name).configure(family=(UI_MONO if _name == 'TkFixedFont' else UI_SANS))
    else:
        UI_SANS = _default.actual('family')
        UI_MONO = _tkfont.nametofont('TkFixedFont').actual('family')
    _scale_override = os.environ.get('BAR_TK_SCALING')
    if _scale_override:
        try:
            root.tk.call('tk', 'scaling', float(_scale_override))
        except (ValueError, tk.TclError):
            pass
    # ----- Window-size floors (single edit point) -------------------------
    # Final window size is max(MIN_*, measured content size). Edit these to
    # taste -- if you want a smaller window, lower the floor. The measure
    # block before mainloop() will still upsize past these if Tk reports a
    # natural content size that won't fit, so the button row can't end up
    # clipped, only the floor moves.
    MIN_W, MIN_H = 480, 620
    # ----------------------------------------------------------------------
    root.geometry(f'{MIN_W}x{MIN_H}')
    root.resizable(True, True)
    root.title('BAR Replay and Debug Launcher')
    try:
        root.iconbitmap('bar-icon.ico')
    except:
        print("Unable to find bar-icon.ico")

    # ttk theme: prefer 'clam' (flat, modern-ish look that ships with stock
    # Tk on Linux/macOS/Windows). Falls back to whatever's available.
    style = ttk.Style()
    for _theme in ('clam', 'alt', 'default'):
        if _theme in style.theme_names():
            try:
                style.theme_use(_theme)
            except tk.TclError:
                continue
            break

    # Custom styles for visual hierarchy.
    style.configure('Hint.TLabel', foreground='#666')
    style.configure('Link.TLabel', foreground='#2563eb')
    style.configure('Section.TLabelframe', padding=10)
    style.configure('Section.TLabelframe.Label', font=(UI_SANS, 10, 'bold'))

    PAD = 8

    # Root uses grid (not pack) so each section sits in its own reserved row.
    # If the config block ever grows beyond expectations, the button row at
    # row=4 still renders -- it can't be pushed off the bottom by overflow
    # above. The cmd/mod text panels never grow (fixed line counts), so no
    # row needs weight=1; weight stays 0 everywhere.
    root.grid_columnconfigure(0, weight=1)

    # Header / preamble: dim explainer on the left, "GitHub" link on the
    # right. Tk has no native hyperlink, so we style a Label with Link.TLabel
    # + hand cursor + click handler that opens the default browser.
    header = ttk.Frame(root)
    header.grid(row=0, column=0, sticky=tk.EW, padx=PAD, pady=(PAD, PAD // 2))
    header.columnconfigure(0, weight=1)
    # No wraplength: let the label keep its natural single-line width so
    # winfo_reqwidth() picks it up and the window grows to match. Pinning
    # wraplength to MIN_W forced wrapping whenever MIN_W < natural width.
    ttk.Label(header,
              text=f"Place this next to {launcher_binary_display} to scan for contents.",
              style='Hint.TLabel', justify=tk.LEFT,
              ).grid(row=0, column=0, sticky=tk.W)
    _GH_URL = "https://github.com/beyond-all-reason/bar_debug_launcher"
    _link = ttk.Label(header, text="GitHub ↗", style='Link.TLabel', cursor='hand2')
    _link.grid(row=0, column=1, sticky=tk.E, padx=(PAD, 0))
    _link.bind('<Button-1>', lambda e: webbrowser.open(_GH_URL))
    _link.bind('<Enter>', lambda e: _link.configure(font=(UI_SANS, 9, 'underline')))
    _link.bind('<Leave>', lambda e: _link.configure(font=(UI_SANS, 9)))

    # ---------------------------------------------------------------------
    # Intent-first config: Engine, then (Play, Source, Boot, Map) in a
    # 2-column grid so labels and widgets line up. The ⓘ-square-button has
    # been replaced with a less-jarring "Details…" link next to the source
    # combobox -- same affordance, calmer presentation.
    # ---------------------------------------------------------------------

    PLAY_LABELS = {
        "chobby": "Chobby (lobby/menu)",
        "bar":    "BAR (game directly)",
        "replay": "Replay…",
    }
    PLAY_BY_LABEL = {v: k for k, v in PLAY_LABELS.items()}

    def _local_available(play):
        if play == "replay":
            return False
        try:
            resolve_intent(Intent(play, "local", default_boot(play)), modinfos)
            return True
        except (KeyError, ValueError):
            return False

    def _pinned_versions(play):
        versions = set()
        if play == "chobby":
            wanted_modtype = {"5", "0"}
        elif play == "bar":
            wanted_modtype = {"1"}
        else:
            return []
        for label, mi in modinfos.items():
            if label.startswith("[LOCAL]"):
                continue
            if str(mi.get("modtype", "")) not in wanted_modtype:
                continue
            m = re.search(r"(\S+)\s+\$VERSION", label)
            if m:
                versions.add(m.group(1))
        return sorted(versions, reverse=True)

    def _local_source_paths(play):
        if play == "replay":
            return []
        gamespath = os.path.join(datafolder, "games")
        if not os.path.isdir(gamespath):
            return []
        wanted_modtype = "1" if play == "bar" else "5"
        out = []
        for gamedir in sorted(os.listdir(gamespath)):
            label = f"[LOCAL] {gamedir}"
            mi = modinfos.get(label)
            if mi and str(mi.get("modtype", "")) == wanted_modtype:
                out.append(os.path.join(gamespath, gamedir))
        return out

    config_frame = ttk.LabelFrame(root, text='What to launch', style='Section.TLabelframe')
    config_frame.grid(row=1, column=0, sticky=tk.EW, padx=PAD, pady=PAD // 2)
    # Column 1 is the wide widget column; column 2 holds inline addons (link).
    config_frame.columnconfigure(1, weight=1)

    # Three orthogonal source axes (engine / chobby / game) each get their
    # own dropdown. Whichever is "active" depends on Play; the inactive ones
    # grey out (state=disabled) but their values persist so toggling Play
    # doesn't blow away your pin on the other axis.
    selected_engine = tk.StringVar()
    selected_play_label = tk.StringVar()
    selected_chobby_source = tk.StringVar()
    selected_game_source = tk.StringVar()
    selected_boot = tk.StringVar()
    selected_map = tk.StringVar()

    def _grid_label(text, row):
        ttk.Label(config_frame, text=text).grid(row=row, column=0, sticky=tk.W, padx=(0, PAD), pady=4)

    # Engine source row -- the engine binary. Always active for chobby/bar;
    # replay overrides via the demo header but the default still comes from here.
    _grid_label("Engine source", 0)
    engine_cb = ttk.Combobox(config_frame, textvariable=selected_engine, state='readonly',
                             height=min(len(engines), 40))
    engine_cb['values'] = sorted(engines.keys())
    _default_engine = next(
        (k for k in engines.keys() if "local-build" in k),
        sorted(engines.keys())[-1],
    )
    engine_cb.set(_default_engine)
    engine_cb.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=4)

    # Play row -- which thing to launch (chobby vs bar vs replay).
    _grid_label("Play", 1)
    play_cb = ttk.Combobox(config_frame, textvariable=selected_play_label, state="readonly",
                           values=[PLAY_LABELS[p] for p in PLAY_CHOICES])
    play_cb.set(PLAY_LABELS["chobby"])
    play_cb.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=4)

    # Chobby source -- active when Play=chobby.
    _grid_label("Chobby source", 2)
    chobby_source_cb = ttk.Combobox(config_frame, textvariable=selected_chobby_source, state="readonly")
    chobby_source_cb.grid(row=2, column=1, columnspan=2, sticky=tk.EW, pady=4)

    # Game source -- active when Play=BAR.
    _grid_label("Game source", 3)
    game_source_cb = ttk.Combobox(config_frame, textvariable=selected_game_source, state="readonly")
    game_source_cb.grid(row=3, column=1, columnspan=2, sticky=tk.EW, pady=4)

    # Boot row
    _grid_label("Boot", 4)
    boot_cb = ttk.Combobox(config_frame, textvariable=selected_boot, state="readonly",
                           values=list(BOOT_CHOICES), width=12)
    boot_cb.grid(row=4, column=1, columnspan=2, sticky=tk.W, pady=4)

    # Map row
    _grid_label("Map", 5)
    map_cb = ttk.Combobox(config_frame, textvariable=selected_map, state='readonly',
                          height=min(len(maps), 50))
    map_cb['values'] = ['Ill choose my own once ingame'] + sorted(maps.keys())
    map_cb.set('Ill choose my own once ingame')
    map_cb.grid(row=5, column=1, columnspan=2, sticky=tk.EW, pady=4)

    # One-line "hover for details" hint under the dropdowns -- a single
    # discoverability cue rather than six separate static helpers.
    ttk.Label(config_frame,
              text="hover any field for technical details · greyed sources are inactive but persist",
              style='Hint.TLabel').grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(PAD // 2, 0))

    # Generated command preview (smaller; full command always visible).
    cmd_frame = ttk.LabelFrame(root, text='Generated command', style='Section.TLabelframe')
    cmd_frame.grid(row=2, column=0, sticky=tk.EW, padx=PAD, pady=PAD // 2)
    # width=1 so Tk doesn't claim the default 80-column natural width as the
    # window's required width -- the LabelFrame stretches via fill=tk.X and
    # the inner Text follows. Without this the Text alone forces ~560px.
    cmdtext = tk.Text(cmd_frame, height=4, width=1, font=(UI_MONO, 9),
                      wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
                      background="#f5f5f5")
    cmdtext.pack(fill=tk.X)

    # Modoptions
    mod_frame = ttk.LabelFrame(root, text='Additional modoptions', style='Section.TLabelframe')
    mod_frame.grid(row=3, column=0, sticky=tk.EW, padx=PAD, pady=PAD // 2)
    modoptionstb = tk.Text(mod_frame, height=3, width=1, font=(UI_MONO, 9),
                           wrap=tk.WORD, relief=tk.FLAT, borderwidth=1)
    modoptionstb.pack(fill=tk.X)

    # ---------------------------------------------------------------------
    # Per-field tooltips. Each text_func is called at hover time so it
    # reflects the *current* selection -- no stale strings.
    # ---------------------------------------------------------------------
    def _engine_tip():
        eng = selected_engine.get()
        path = engines.get(eng, '?')
        note = ("Local dev build (linked into <data-dir>/engine/local-build/)."
                if "local-build" in eng
                else "Cached engine release.")
        return (f"Engine: {eng}\n"
                f"Binary: {path}\n\n{note}\n\n"
                "Used as the spring(.exe) executable; passed --isolation "
                "and --write-dir <data-dir> regardless of how it boots.")

    def _play_tip():
        play = PLAY_BY_LABEL.get(selected_play_label.get(), '?')
        return {
            'chobby': ("Chobby — the lobby/menu (room browser, settings, replays).\n\n"
                       "Resolves to a 'menu' archive: modtype 0 when booting via the "
                       "AppImage launcher, modtype 5 when booting the engine directly "
                       "with --menu."),
            'bar':    ("Beyond All Reason game directly (skirmish, debugging).\n\n"
                       "Resolves to a 'game' archive (modtype 1). The launcher writes "
                       "bar_debug_launcher_script.txt with the chosen map and the engine "
                       "reads that as its start script."),
            'replay': (".sdfz replay file. The Play dropdown sets the mode but the file "
                       "itself is picked via the 'Open and launch a replay' button below. "
                       "Engine version is taken from the demo header, not the Engine "
                       "dropdown above."),
        }.get(play, '')

    def _source_axis_tip(axis_play, source_var):
        # Shared body for the chobby/game source tooltips. axis_play is the
        # play this dropdown represents ("chobby" or "bar"); source_var is
        # its StringVar. The tooltip flags whether the axis is currently
        # active for the launch (Play matches) so the user can tell at a
        # glance which dropdown drives the resolved command.
        active_play = PLAY_BY_LABEL.get(selected_play_label.get(), '?')
        active = (active_play == axis_play)
        src_kind, src_arg = _parse_source(source_var.get())
        boot = selected_boot.get() or default_boot(axis_play)
        what = "Chobby (lobby/menu)" if axis_play == "chobby" else "BAR (game)"
        head = (f"{what} source — ACTIVE for this launch.\n\n" if active
                else f"{what} source — inactive (Play is set to {active_play!r}). "
                     f"Value persists for when you switch back.\n\n")
        head += {
            'latest': f"Latest test channel — pulled at run time via "
                      f"{'rapid://byar-chobby:test' if axis_play == 'chobby' else 'rapid://byar:test'}.",
            'local':  f"Local {what} checkout — a working tree linked into <data-dir>/games/.",
            'pinned': f"Pinned cached {what} version ({src_arg or '?'}).",
        }.get(src_kind, '')
        try:
            label, mi = resolve_intent(Intent(axis_play, src_kind, boot, version=src_arg), modinfos)
            body = (f"\n\nResolves to: {label}\n"
                    f"Archive name: {mi.get('name', '?')}\n"
                    f"modtype: {mi.get('modtype', '?')} "
                    f"({'AppImage launcher' if mi.get('modtype') == '0' else 'engine direct'})")
        except (KeyError, ValueError) as e:
            body = f"\n\nResolve error: {e}"
        if src_kind == 'local':
            paths = _local_source_paths(axis_play)
            if paths:
                body += "\n\nCheckout: " + paths[0]
        return head + body

    def _chobby_source_tip(): return _source_axis_tip("chobby", selected_chobby_source)
    def _game_source_tip():   return _source_axis_tip("bar",    selected_game_source)

    def _boot_tip():
        return {
            'launcher': ("Boot via Beyond-All-Reason.AppImage.\n\n"
                         "Writes a dev-lobby JSON, then runs the AppImage with -c <config>. "
                         "The AppImage handles splash, auto-update, and rapid:// downloads "
                         "of any missing assets. Slower start, but matches the real-player "
                         "experience."),
            'engine':   ("Boot the engine binary directly.\n\n"
                         "Runs spring(.exe) with --menu <name> (chobby) or a generated "
                         "start script (bar). Faster, no launcher overhead, but breaks if "
                         "any assets are missing — there's no download retry layer."),
        }.get(selected_boot.get(), '')

    def _map_tip():
        play = PLAY_BY_LABEL.get(selected_play_label.get(), '?')
        if play != 'bar':
            return "Map is only used when Play = BAR. Ignored for chobby and replays."
        mp = selected_map.get()
        if mp == 'Ill choose my own once ingame':
            return ("No map preselected.\n\nThe engine starts without a start script; "
                    "you'll choose a map from the in-game skirmish menu.")
        return (f"Map: {mp}\n\nWill write bar_debug_launcher_script.txt containing a "
                "[game] block with mapname=<this>, gametype=<resolved game name>, and "
                "any modoptions you've added below. Engine reads that as its start "
                "script and goes straight into the match.")

    _Tooltip(engine_cb,        _engine_tip)
    _Tooltip(play_cb,          _play_tip)
    _Tooltip(chobby_source_cb, _chobby_source_tip)
    _Tooltip(game_source_cb,   _game_source_tip)
    _Tooltip(boot_cb,          _boot_tip)
    _Tooltip(map_cb,           _map_tip)

    def _parse_source(s):
        if s == "Latest":
            return ("latest", None)
        if s.startswith("Local checkout"):
            return ("local", None)
        if s.startswith("Pinned: "):
            return ("pinned", s[len("Pinned: "):])
        return ("latest", None)

    def _source_options_for(play):
        """Return (opts list, default-local-opt-if-any) for one source axis."""
        opts = ["Latest"]
        local_opt = None
        if _local_available(play):
            paths = _local_source_paths(play)
            tag = paths[0] if paths else "<unknown path>"
            local_opt = f"Local checkout ({tag})"
            opts.append(local_opt)
        for v in _pinned_versions(play):
            opts.append(f"Pinned: {v}")
        return opts, local_opt

    def _populate_chobby_sources():
        opts, local_opt = _source_options_for("chobby")
        chobby_source_cb['values'] = opts
        if selected_chobby_source.get() not in opts:
            selected_chobby_source.set(local_opt or opts[0])

    def _populate_game_sources():
        opts, local_opt = _source_options_for("bar")
        game_source_cb['values'] = opts
        if selected_game_source.get() not in opts:
            selected_game_source.set(local_opt or opts[0])

    def _refresh_states():
        """Grey out the source dropdowns / Map / Boot that don't apply to
        the current Play. The disabled state preserves the StringVar's value
        -- it's strictly visual + click-blocking."""
        play = PLAY_BY_LABEL.get(selected_play_label.get(), "chobby")
        chobby_source_cb.configure(state="readonly" if play == "chobby" else "disabled")
        game_source_cb.configure(state="readonly" if play == "bar" else "disabled")
        map_cb.configure(state="readonly" if play == "bar" else "disabled")
        boot_cb.configure(state="readonly" if play in ("chobby", "bar") else "disabled")
        engine_cb.configure(state="readonly" if play != "replay" else "disabled")

    _populate_chobby_sources()
    _populate_game_sources()
    selected_boot.set(default_boot("chobby"))

    runcmd = ""

    def _ctx():
        # Wrap the GUI's existing globals as a Context so we can reuse the
        # CLI's command builder. build_runcmd is the canonical place that
        # encodes how (modinfo, engine, map) becomes the engine invocation.
        return Context(
            barinstallpath=barinstallpath,
            datafolder=datafolder,
            launcher_binary=launcher_binary,
            engines=engines,
            modinfos=modinfos,
        )

    def gencmd(event=None):
        global runcmd
        play = PLAY_BY_LABEL.get(selected_play_label.get(), "chobby")
        if play == "replay":
            runcmd = ""
            cmdtext.delete('1.0', tk.END)
            cmdtext.insert('1.0', "Use the 'Open and launch a replay' button below.")
            return
        # Pick the active source axis for this Play. The other source
        # dropdown's value is ignored by this launch but stays set for next
        # time (see _refresh_states for the visual greying).
        if play == "chobby":
            src_str = selected_chobby_source.get()
        else:  # bar
            src_str = selected_game_source.get()
        src_kind, src_arg = _parse_source(src_str)
        boot = selected_boot.get() or default_boot(play)
        try:
            label, modinfo = resolve_intent(
                Intent(play, src_kind, boot, version=src_arg), modinfos
            )
        except (KeyError, ValueError) as e:
            runcmd = ""
            cmdtext.delete('1.0', tk.END)
            cmdtext.insert('1.0', f"# could not resolve intent: {e}")
            return
        myengine = selected_engine.get()
        mymap = selected_map.get()
        modopts = modoptionstb.get('1.0', tk.END)
        try:
            runcmd = build_runcmd(_ctx(), modinfo, myengine, mymap, modopts)
        except (KeyError, ValueError) as e:
            runcmd = ""
            cmdtext.delete('1.0', tk.END)
            cmdtext.insert('1.0', f"# build_runcmd error: {e}")
            return
        print(f"[{label}]", runcmd)
        cmdtext.delete('1.0', tk.END)
        cmdtext.insert('1.0', str(runcmd))

    def _on_play_changed(event=None):
        play = PLAY_BY_LABEL.get(selected_play_label.get(), "chobby")
        # Re-default boot for the new play; user can still override.
        if play != "replay":
            selected_boot.set(default_boot(play))
        _refresh_states()
        gencmd()

    engine_cb.bind('<<ComboboxSelected>>',        gencmd)
    play_cb.bind('<<ComboboxSelected>>',          _on_play_changed)
    chobby_source_cb.bind('<<ComboboxSelected>>', gencmd)
    game_source_cb.bind('<<ComboboxSelected>>',   gencmd)
    boot_cb.bind('<<ComboboxSelected>>',          gencmd)
    map_cb.bind('<<ComboboxSelected>>',           gencmd)

    # Initial state-toggle + first command render.
    _refresh_states()

    def startreplay():
        filetypes = [('BAR Replay Files', '*.sdfz'),
                    ('All files', '*.*')]
        filename = filedialog.askopenfilename(title='Select a replay to watch',
                                              initialdir=os.path.join(barinstallpath, datafolder, 'demos'),
                                              filetypes=filetypes)
        print(filename)
        if filename:
            try_start_replay(filename)

    def startspring():
        gencmd(None)
        print('starting spring with', runcmd)
        subprocess.Popen(host_cmd_prefix() + shlex.split(runcmd), close_fds=True)

    button_frame = ttk.Frame(root)
    button_frame.grid(row=4, column=0, sticky=tk.EW, padx=PAD, pady=(PAD // 2, PAD))
    button_frame.columnconfigure(0, weight=1)
    button_frame.columnconfigure(1, weight=1)
    ttk.Button(button_frame, text="Open and launch a replay…",
               command=startreplay).grid(row=0, column=0, sticky=tk.EW, padx=(0, PAD // 2))
    # Primary action: emphasize via ttk.Style (TButton can't easily get a
    # bold variant without a custom style, so we use a slightly bolder label).
    style.configure('Primary.TButton', font=(UI_SANS, 10, 'bold'))
    ttk.Button(button_frame, text="▶  Launch with selected settings",
               style='Primary.TButton',
               command=startspring).grid(row=0, column=1, sticky=tk.EW, padx=(PAD // 2, 0))

    gencmd(None)  # init defaults

    # Hard sizing: ask Tk what each widget actually rendered to (which captures
    # theme padding, system font DPI, HiDPI scaling -- everything the
    # estimated-by-eyeball geometry hint above gets wrong) and size the window
    # from that, with a floor. Without this, on themes/DPIs where comboboxes
    # render taller than expected, the bottom rows get pushed off-screen.
    root.update_idletasks()
    req_w = root.winfo_reqwidth()
    req_h = root.winfo_reqheight()
    # MIN_W/MIN_H are floors -- final size is at least MIN_*, but grows
    # past that if natural content needs more room. This makes the window
    # wide enough to fit the header without wrapping, regardless of MIN_W.
    # If you want hard MIN_* (no auto-grow), replace `max(...)` with the
    # MIN_* literal.
    win_w = max(MIN_W, req_w + 8)
    win_h = max(MIN_H, req_h + 8)
    # minsize first so the WM has the lower bound. Schedule the resize via
    # after_idle so it runs AFTER Tk's auto-fit-to-content pass -- otherwise
    # Tk shrinks the window back to natural content size when our requested
    # width exceeds it (the "MIN_W up doesn't work" failure).
    root.minsize(win_w, win_h)
    root.after_idle(lambda: root.geometry(f"{win_w}x{win_h}"))
    root.mainloop()
else:
    #arg passed, it better be a replay file
    print("Arguments are:", sys.argv)
    replayfilepath = sys.argv[1]
    try_start_replay(replayfilepath)
