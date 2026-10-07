from __future__ import annotations

DESCRIPTION = """聚合 dgstudio-modules-* 子仓库，生成模块市场清单 market.yaml。

DGStudio「模块」页只读取本文件（总仓库根的 market.yaml），不直接访问
各子仓库。清单由 GitHub Actions 定期重建，也可本地生成后提交：

    # CI / 联网：经 GitHub API 发现 owner 名下 dgstudio-modules-* 仓库
    GITHUB_TOKEN=xxx python _tools/build_market.py --owner KelierAndes

    # 本地离线：扫描目录下匹配前缀的仓库文件夹（如 D:\\ 下的各仓库）
    python _tools/build_market.py --local D:\\

规则（与 AstrBot 插件仓库一致的模式）：
* 每个模块一个独立仓库，命名 dgstudio-modules-<模块 id>；
* 仓库根必须含 plugin.py（META 纯字面量），可选 requirements.txt
  （pip 依赖串，「!」前缀 = 可选依赖 --no-deps 安装）、README.md；
* 输出按模块 id 排序，字符串以 JSON 风格双引号写入（合法 YAML）。
"""

import argparse
import ast
import base64
import io
import json
import os
import sys
import time
import urllib.request

DEFAULT_OWNER = "KelierAndes"
DEFAULT_PREFIX = "dgstudio-modules-"
MASTER_REPO = "dgstudio-modules-market"
DEFAULT_BRANCH = "main"
SKIP_DIRS = {".git", "__pycache__", "_deps"}
SKIP_SUFFIX = (".downloading", ".old")
USER_AGENT = "DGStudio-MarketBuilder/1.0"


def read_meta(plugin_py_text: str) -> dict:
    import re

    tree = ast.parse(plugin_py_text)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "META":
                value = ast.literal_eval(node.value)
                return value if isinstance(value, dict) else {}
    raise ValueError("plugin.py 未找到 META 字面量")


def parse_requirements(text: str) -> list[str]:
    out: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def is_skipped(name: str) -> bool:
    return (name in SKIP_DIRS or name.endswith(SKIP_SUFFIX)
            or name.endswith(".pyc") or name.endswith(".pyo"))


def build_entry(repo: str, meta: dict, requirements: list[str],
                files: list[str], branch: str, author: str,
                path: str = "") -> dict:
    module_id = str(meta.get("id") or "")
    if not module_id:
        raise ValueError("META 缺少 id")
    return {
        "id": module_id,
        "repo": repo,
        "path": path,
        "branch": branch or DEFAULT_BRANCH,
        "author": author,
        "name": str(meta.get("name") or module_id),
        "version": str(meta.get("version") or "0.0.0"),
        "description": str(meta.get("description") or ""),
        "default_enabled": bool(meta.get("default_enabled", False)),
        "requirements": requirements,
        "files": files,
    }


def _y(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def emit_market(entries: list[dict], out_path: str) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lines = [
        "# DGStudio 模块市场清单 —— 由 _tools/build_market.py 自动生成，勿手动编辑。",
        f"schema: 1",
        f'generated: "{now}"',
        f'source: "https://github.com/{DEFAULT_OWNER}/{MASTER_REPO}"',
        "modules:",
    ]
    for entry in sorted(entries, key=lambda e: e["id"]):
        lines.append(f"  - id: {_y(entry['id'])}")
        lines.append(f"    repo: {_y(entry['repo'])}")
        lines.append(f"    path: {_y(entry.get('path') or '')}")
        lines.append(f"    branch: {_y(entry['branch'])}")
        lines.append(f"    author: {_y(entry['author'])}")
        lines.append(f"    name: {_y(entry['name'])}")
        lines.append(f"    version: {_y(entry['version'])}")
        lines.append(f"    description: {_y(entry['description'])}")
        lines.append(f"    default_enabled: {'true' if entry['default_enabled'] else 'false'}")
        lines.append(f"    requirements: {_y(entry['requirements'])}")
        lines.append(f"    files: {_y(entry['files'])}")
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def find_module_dir(repo_dir: str) -> str:
    if os.path.isfile(os.path.join(repo_dir, "plugin.py")):
        return ""
    for entry in sorted(os.listdir(os.path.join(repo_dir, "modules")))             if os.path.isdir(os.path.join(repo_dir, "modules")) else []:
        if os.path.isfile(os.path.join(repo_dir, "modules", entry, "plugin.py")):
            return f"modules/{entry}"
    raise FileNotFoundError(f"{repo_dir} 未找到 plugin.py（根目录或 modules/*/）")


def collect_local(repo_dir: str, owner: str) -> dict:
    repo = os.path.basename(os.path.normpath(repo_dir))
    rel = find_module_dir(repo_dir)
    mod_dir = os.path.join(repo_dir, rel) if rel else repo_dir
    plugin_py = os.path.join(mod_dir, "plugin.py")
    if not os.path.isfile(plugin_py):
        raise FileNotFoundError(f"{repo} 缺少 plugin.py")
    with io.open(plugin_py, encoding="utf-8") as f:
        meta = read_meta(f.read())
    req_path = os.path.join(mod_dir, "requirements.txt")
    requirements: list[str] = []
    if os.path.isfile(req_path):
        with io.open(req_path, encoding="utf-8") as f:
            requirements = parse_requirements(f.read())
    files: list[str] = []
    for cur, dirs, names in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if not is_skipped(d)]
        for name in sorted(names):
            if is_skipped(name):
                continue
            files.append(os.path.relpath(os.path.join(cur, name),
                                         repo_dir).replace(os.sep, "/"))
    return build_entry(repo, meta, requirements, sorted(files),
                       DEFAULT_BRANCH, owner, path=rel)


def discover_local(base_dir: str, prefix: str) -> list[str]:
    found: list[str] = []
    for name in sorted(os.listdir(base_dir)):
        path = os.path.join(base_dir, name)
        if not name.startswith(prefix) or not os.path.isdir(path):
            continue
        try:
            find_module_dir(path)
        except FileNotFoundError:
            continue
        found.append(path)
    return found


def _http_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_text(url: str, token: str) -> str:
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as resp:
        return resp.read().decode("utf-8")


def discover_remote(owner: str, prefix: str, token: str) -> list[str]:
    query = f"user:{owner}+{prefix}+in:name&per_page=100"
    payload = _http_json(
        f"https://api.github.com/search/repositories?q={query}", token)
    repos = []
    for item in payload.get("items") or []:
        name = str(item.get("name") or "")
        if name.startswith(prefix) and name != MASTER_REPO:
            repos.append(name)
    return sorted(repos)


def collect_remote(owner: str, repo: str, token: str) -> dict:
    info = _http_json(f"https://api.github.com/repos/{owner}/{repo}", token)
    branch = str(info.get("default_branch") or DEFAULT_BRANCH)
    blobs: dict[str, str] = {}

    def blob_text(path: str) -> str:
        sha = blobs.get(path)
        if sha:
            payload = _http_json(
                f"https://api.github.com/repos/{owner}/{repo}"
                f"/git/blobs/{sha}", token)
            return base64.b64decode(payload.get("content") or "").decode("utf-8")
        return _http_text(
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
            token)

    files: list[str] = []
    try:
        tree = _http_json(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
            f"?recursive=1", token)
        blobs = {item["path"]: item["sha"]
                 for item in tree.get("tree") or []
                 if item.get("type") == "blob"}
        if not tree.get("truncated"):
            files = sorted(path for path in blobs if not is_skipped(path))
    except Exception:
        files = []
    rel = ""
    if "plugin.py" not in blobs:
        for name in files:
            if name.startswith("modules/") and name.endswith("/plugin.py")                     and name.count("/") == 2:
                rel = name.rsplit("/plugin.py", 1)[0]
                break
    base = f"{rel}/" if rel else ""
    meta = read_meta(blob_text(f"{base}plugin.py"))
    requirements: list[str] = []
    if f"{base}requirements.txt" in blobs or rel == "":
        try:
            requirements = parse_requirements(
                blob_text(f"{base}requirements.txt"))
        except Exception:
            requirements = []
    return build_entry(repo, meta, requirements, files, branch,
                       str(info.get("owner", {}).get("login") or owner),
                       path=rel)


def main() -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--out", default="market.yaml")
    parser.add_argument("--sources", default="sources.txt",
                        help="手工兜底清单（每行一个仓库名，# 注释）")
    parser.add_argument("--local", default="",
                        help="本地模式：扫描该目录下匹配前缀的仓库文件夹")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    entries: dict[str, dict] = {}
    if args.local:
        repo_dirs = discover_local(args.local, args.prefix)
        if not repo_dirs:
            print(f"[错误] {args.local} 下未发现 {args.prefix}* 仓库文件夹",
                  file=sys.stderr)
            return 1
        for repo_dir in repo_dirs:
            entry = collect_local(repo_dir, args.owner)
            entries[entry["repo"]] = entry
            print(f"[模块] {entry['id']} v{entry['version']} ← {entry['repo']}"
                  f"（本地）")
    else:
        repos: list[str] = set()
        try:
            found = discover_remote(args.owner, args.prefix, token)
            print(f"[发现] GitHub API 命中 {len(found)} 个仓库")
            repos.update(found)
        except Exception as exc:
            print(f"[警告] GitHub API 发现失败（{exc}）", file=sys.stderr)
        if os.path.isfile(args.sources):
            with io.open(args.sources, encoding="utf-8") as f:
                listed = [line.strip() for line in f
                          if line.strip() and not line.strip().startswith("#")]
            print(f"[发现] sources.txt 提供 {len(listed)} 个仓库")
            repos.update(listed)
        repos = sorted(repos)
        failures = 0
        for repo in repos:
            try:
                entry = collect_remote(args.owner, repo, token)
                entries[entry["repo"]] = entry
                print(f"[模块] {entry['id']} v{entry['version']} ← {repo}")
            except Exception as exc:
                failures += 1
                print(f"[错误] 解析 {repo} 失败: {exc}", file=sys.stderr)
        if repos and failures == len(repos):
            print("[错误] 全部子仓库解析失败", file=sys.stderr)
            return 1

    if not entries:
        print("[错误] 未生成任何模块条目", file=sys.stderr)
        return 1
    emit_market(list(entries.values()), args.out)
    print(f"已写入 {args.out}（{len(entries)} 个模块）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
