import os
import importlib.util
import sys
import re
import json
import requests
from pathlib import Path

from config import PLUGINS_DIR, logger

LOADED_PLUGINS = []
_plugins_loaded = False

def load_plugins(force=False):
    global _plugins_loaded
    if _plugins_loaded and not force:
        return LOADED_PLUGINS
    if force:
        LOADED_PLUGINS.clear()
    if not os.path.isdir(PLUGINS_DIR):
        return []
    for fn in sorted(os.listdir(PLUGINS_DIR)):
        if fn.startswith("plugin_") and fn.endswith(".py") and fn != "plugin_base.py":
            try:
                spec = importlib.util.spec_from_file_location(fn[:-3], os.path.join(PLUGINS_DIR, fn))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "GET_AGENT_PLUGIN_CLASS"):
                    klass = mod.GET_AGENT_PLUGIN_CLASS()
                    if hasattr(klass, "command_names"):
                        klass._source_file = fn
                        LOADED_PLUGINS.append(klass)
                        logger.info(f"Plugin chargé: {fn}")
            except Exception as e:
                logger.error(f"Plugin {fn} fail: {e}")
    _plugins_loaded = True
    return LOADED_PLUGINS

def plugin_handle(uin):
    for pl in LOADED_PLUGINS:
        for cmd in pl.command_names:
            if uin.startswith(cmd):
                try:
                    return pl.execute(uin)
                except Exception as e:
                    return f"[Erreur Plugin] {e}"
    return None

# --- Connecteurs ---
from config import WS_DIR
CONNECTORS_PATH = WS_DIR / "connectors.json"

def connectors_load():
    if not CONNECTORS_PATH.exists():
        return []
    try:
        with open(CONNECTORS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Connectors load fail: {e}")
        return []

def connectors_save(lst):
    try:
        with open(CONNECTORS_PATH, "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Connectors save fail: {e}")

def connector_handle(uin):
    for c in connectors_load():
        cmd = c.get("command", "")
        if cmd and uin.startswith(cmd):
            try:
                url = c.get("base_url", "")
                headers = {}
                if c.get("api_key"):
                    headers[c.get("header_name") or "Authorization"] = f"{c.get('header_prefix', 'Bearer ')}{c['api_key']}"
                query = uin[len(cmd):].strip()
                if c.get("method", "GET").upper() == "POST":
                    r = requests.post(url, headers=headers, json={"query": query}, timeout=15)
                else:
                    r = requests.get(url, headers=headers, params={"q": query} if query else None, timeout=15)
                r.raise_for_status()
                try:
                    return json.dumps(r.json(), ensure_ascii=False, indent=2)[:4000]
                except Exception:
                    return r.text[:4000]
            except Exception as e:
                logger.error(f"Connecteur {c.get('name')} fail: {e}")
                return f"[Erreur connecteur {c.get('name')}] {e}"
    return None
