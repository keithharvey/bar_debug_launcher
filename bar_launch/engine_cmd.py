"""Pure command-string construction. Shared by GUI gencmd and CLI."""
from __future__ import annotations

import json
import os
from typing import Optional

from .core import Context

SCRIPT_BASE = """
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


def write_start_script(modopts: str, mapname: str, gamename: str, path: str = "bar_debug_launcher_script.txt") -> str:
    """Write the engine start script. Returns the path written."""
    script = SCRIPT_BASE % (modopts, mapname, gamename)
    with open(path, "w") as f:
        f.write(script)
    print("Generated script:", script)
    return path


def write_dev_lobby_config(
    engine_version: str,
    mod_name: str,
    path: str = "bar_debug_launcher_config.json",
) -> str:
    """Write the spring-launcher dev-lobby config. Returns the path written."""
    config = {
        "title": "Beyond All Reason",
        "setups": [
            {
                "package": {"id": "dev-lobby", "display": "Dev Lobby"},
                "downloads": {"engines": [engine_version]},
                "no_start_script": True,
                "no_downloads": True,
                "auto_start": True,
                "launch": {"start_args": ["--menu", mod_name]},
            }
        ],
    }
    with open(path, "w") as f:
        json.dump(config, f, indent=4)
    return path


def build_runcmd(
    ctx: Context,
    modinfo: dict,
    engine_version: str,
    mapname: Optional[str] = None,
    modopts: str = "",
    script_path: str = "bar_debug_launcher_script.txt",
    config_path: str = "bar_debug_launcher_config.json",
) -> str:
    """Build the engine command string for a given (modinfo, engine, map) triple.

    `engine_version` is a key into ctx.engines (e.g. "recoil_2025.06.19" or
    "105.1.1-941-g941148f bar"). Returns the shell command string; the caller
    is responsible for executing or printing it.
    """
    write_dir = os.path.join(ctx.barinstallpath, ctx.datafolder)
    enginepath = ctx.engines.get(engine_version)
    if enginepath is None:
        raise KeyError(f"engine {engine_version!r} not in ctx.engines")

    mtype = modinfo["modtype"]
    if mtype == "5":
        return f'"{enginepath}"  --isolation --write-dir "{write_dir}" --menu "{modinfo["name"]}"'
    if mtype == "1":
        if mapname and mapname != "Ill choose my own once ingame":
            write_start_script(modopts, mapname, modinfo["name"], script_path)
            return f'"{enginepath}"  --isolation --write-dir "{write_dir}" {script_path}'
        return f'"{enginepath}"  --isolation --write-dir "{write_dir}"'
    if mtype == "0":
        write_dev_lobby_config(engine_version, modinfo["name"], config_path)
        return f'"{os.path.join(ctx.barinstallpath, ctx.launcher_binary)}" -c "{os.path.join(ctx.barinstallpath, config_path)}"'
    raise ValueError(f"unknown modtype {mtype!r}")
