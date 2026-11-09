#!/usr/bin/env python3
"""M4：FreePPT <-> ppt-master 编译器桥接。

ppt-master 作为【外部前置依赖】，不打包进 FreePPT。本模块负责：
  1. 定位已安装的 ppt-master（用户级 skill 目录；可用 FREEPPT_PPTMASTER 覆盖）
  2. 修复 WorkBuddy shim 里 pathlib.Path.mkdir(exist_ok=True) 的平台 bug（运行期
     monkeypatch，不改动 ppt-master 任何源码）
  3. 调用其 svg_quality_checker（final 阶段）与 svg_to_pptx
"""
import os
import pathlib
import runpy
import sys

_PATCHED = False


def _patch_mkdir():
    global _PATCHED
    if _PATCHED:
        return
    def _fixed_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        if parents:
            os.makedirs(self, mode, exist_ok=exist_ok)
            return
        try:
            os.mkdir(self, mode)
        except FileExistsError:
            if not exist_ok:
                raise
            if not self.is_dir():
                raise
    pathlib.Path.mkdir = _fixed_mkdir
    _PATCHED = True


def pptmaster_root():
    """返回 ppt-master 根目录 Path；找不到返回 None。"""
    env = os.environ.get("FREEPPT_PPTMASTER")
    candidates = []
    if env:
        candidates.append(pathlib.Path(env))
    home = pathlib.Path.home()
    candidates += [
        home / ".workbuddy" / "skills" / "ppt-master",
        home / ".workbuddy" / "plugins" / "cache" / "ppt-master",
    ]
    for c in candidates:
        if (c / "scripts" / "svg_to_pptx.py").is_file():
            return c
    return None


def _run_script(script_path, argv):
    _patch_mkdir()
    sys.argv = [str(script_path)] + [str(a) for a in argv]
    runpy.run_path(str(script_path), run_name="__main__")


def require_root():
    root = pptmaster_root()
    if root is None:
        raise FileNotFoundError(
            "未找到 ppt-master。请先安装该 skill，或设置环境变量 "
            "FREEPPT_PPTMASTER 指向其根目录（须含 scripts/svg_to_pptx.py）。")
    return root


def run_quality_check(project_dir):
    """跑 ppt-master final 阶段质量检查（canonical authoring）。"""
    root = require_root()
    checker = root / "scripts" / "svg_quality_checker.py"
    _run_script(checker, [str(project_dir), "--canonical-authoring",
                          "--stage", "final", "--json"])
    return 0


def run_compile(project_dir, output, *, skip_quality=False):
    """先过质量闸再编译为原生 pptx。返回 0。"""
    if not skip_quality:
        run_quality_check(project_dir)
    root = require_root()
    compiler = root / "scripts" / "svg_to_pptx.py"
    _run_script(compiler, [str(project_dir), "-o", str(output)])
    return 0
