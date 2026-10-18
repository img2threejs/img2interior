#!/usr/bin/env python3
"""Exercise official img2 installation without touching the real user's hosts."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def verify(plugin, harness, cli=None):
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js >=18 is required")
    cli = cli or harness / "bin" / "img2.mjs"
    if not (harness / ".git").exists():
        raise ValueError("--harness-source must be a Git checkout of img2")
    if not cli.is_file():
        raise ValueError("img2 CLI entrypoint does not exist: " + str(cli))
    identity = json.loads((plugin / "plugin.json").read_text(encoding="utf-8"))["name"]
    if identity != "interior":
        raise ValueError("this verifier expects the interior plugin")
    generated = [plugin / "_img2_local.py", plugin / "tools" / "_img2_local.py"]
    original = {p: p.read_bytes() if p.exists() else None for p in generated}
    observations = []
    try:
        with tempfile.TemporaryDirectory(prefix="img2-interior-install-") as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            img2_home = home / ".img2"
            hosts = [home / ".claude", home / ".codex", home / ".config" / "opencode"]
            for host in hosts:
                host.mkdir(parents=True)
            launcher = home / ".local" / "bin"
            launcher.mkdir(parents=True)
            settings_file = home / ".claude" / "settings.json"
            settings_file.write_text(json.dumps({"theme":"preserve-me","permissions":{"allow":["Read"],"additionalDirectories":["/preserved-directory"]}}), encoding="utf-8")
            env = dict(os.environ, HOME=str(home), IMG2_HOME=str(img2_home), XDG_CONFIG_HOME=str(home / ".config"), NO_COLOR="1")
            # Exclude real launcher candidates (/opt/homebrew/bin and /usr/local/bin).
            env["PATH"] = os.pathsep.join(dict.fromkeys([str(launcher), str(Path(node).parent), str(Path(sys.executable).parent), "/usr/bin", "/bin"]))
            env.pop("IMG2THREEJS_HOME", None)

            def run(*args):
                proc = subprocess.run([node, str(cli), *args], env=env, cwd=tmp, capture_output=True, text=True, timeout=120)
                if proc.returncode:
                    raise RuntimeError("img2 %s exited %s\n%s\n%s" % (" ".join(args), proc.returncode, proc.stdout, proc.stderr))
                observations.append({"command":["img2", *args], "exitCode":proc.returncode})
                return proc.stdout

            run("install", "--from", str(harness), "--yes")
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
            if settings.get("theme") != "preserve-me" or settings["permissions"].get("allow") != ["Read"]:
                raise RuntimeError("harness changed unrelated host settings")
            if not {"/preserved-directory", str(img2_home)}.issubset(settings["permissions"]["additionalDirectories"]):
                raise RuntimeError("harness lost or failed to merge directory permissions")
            run("add", "--link", str(plugin), "--yes")
            registry = json.loads((img2_home / "plugins.json").read_text(encoding="utf-8"))
            rows = [r for r in registry["plugins"] if r["id"] == identity]
            if len(rows) != 1 or rows[0]["repo"] != "link:" + str(plugin):
                raise RuntimeError("local source registry identity is wrong")
            canonical = img2_home / "plugins" / identity
            links = []
            for host in hosts:
                link = host / "skills" / ("img2-" + identity)
                if not link.is_symlink() or Path(os.readlink(link)) != canonical or link.resolve() != plugin:
                    raise RuntimeError("incorrect host skill link: %s" % link)
                links.append(str(link.relative_to(home)))
            doctor = json.loads(run("doctor", "--json"))
            if doctor["fails"]:
                raise RuntimeError("static doctor findings: " + json.dumps(doctor))
            run("sync", "--check")
            capability = json.loads(run("capabilities", "--from-kind", "image", "--to-kind", "interior-scene-candidate", "--plugin", identity, "--json"))
            providers = capability.get("providers", [])
            if capability.get("status") != "answered" or len(providers) != 1 or providers[0].get("plugin") != identity:
                raise RuntimeError("capability not resolved: " + json.dumps(capability))
            steps = providers[0]["steps"]
            if not any("instruction" in s and "argv" not in s for s in steps) or not any("argv" in s for s in steps):
                raise RuntimeError("capability lost actor distinction between authored work and programs")
            run("update", identity, "--check")
            run("remove", identity, "--yes")
            if not plugin.is_dir() or not (plugin / "plugin.json").is_file():
                raise RuntimeError("removal damaged original plugin source")
            if any((h / "skills" / ("img2-" + identity)).is_symlink() for h in hosts):
                raise RuntimeError("removal left owned host links")
            if json.loads((img2_home / "plugins.json").read_text(encoding="utf-8"))["plugins"]:
                raise RuntimeError("removal retained registration")
            return {"status":"passed", "plugin":identity, "harnessVersion":json.loads((harness / "package.json").read_text())["version"], "hosts":links, "doctor":doctor, "stepActorsPreserved":True, "originalCheckoutPreserved":True, "commands":observations}
    finally:
        for path, content in original.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness-source", type=Path, required=True)
    parser.add_argument("--plugin-dir", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--cli", type=Path, help="Optional published img2 JavaScript entrypoint; defaults to the source checkout CLI")
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.plugin_dir.resolve(), args.harness_source.resolve(),
                                args.cli.resolve() if args.cli else None), indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status":"error", "reason":str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
