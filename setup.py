"""Setup script for skyborn-plot (pure C99 Meson extensions, zero Fortran deps)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from setuptools import Distribution, setup
from setuptools.command.build_ext import build_ext
from setuptools.command.develop import develop
from setuptools.command.install import install
from setuptools.command.install_lib import install_lib
from wheel.bdist_wheel import bdist_wheel


def _active_python_prefix() -> Path:
    """Return the active interpreter environment prefix."""
    return Path(sys.prefix).resolve()


def _parse_build_only_filter() -> set[str] | None:
    """Parse SKYBORN_BUILD_ONLY comma-separated module filter if set."""
    raw = os.environ.get("SKYBORN_BUILD_ONLY", "").strip()
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


class MesonBuildExt(build_ext):
    """Build pure-C Meson extensions with incremental Ninja cache support."""

    @staticmethod
    def _resolve_tool_command(executable_name: str, module_name: str, *args: str):
        executable_path = shutil.which(executable_name)
        if executable_path:
            return [executable_path, *args]
        return [sys.executable, "-m", module_name, *args]

    @staticmethod
    def _meson_command(*args: str):
        return MesonBuildExt._resolve_tool_command(
            "meson", "mesonbuild.mesonmain", *args
        )

    @staticmethod
    def _ninja_command(*args: str):
        return MesonBuildExt._resolve_tool_command("ninja", "ninja", *args)

    @staticmethod
    def _write_meson_native_file(build_dir: Path) -> Path:
        native_file = (build_dir / "meson-python-native.ini").resolve()
        python_executable = Path(os.path.abspath(sys.executable)).as_posix()
        native_file.write_text(
            "[binaries]\n"
            f"python = '{python_executable}'\n"
            f"build_python = '{python_executable}'\n",
            encoding="utf-8",
        )
        return native_file

    @staticmethod
    def _write_build_python_shim(build_dir: Path) -> Path:
        python_executable = shutil.which("python") or os.path.abspath(sys.executable)
        if os.name == "nt":
            shim_path = (build_dir / "build_python.bat").resolve()
            with shim_path.open("w", encoding="utf-8", newline="\r\n") as handle:
                handle.write("@echo off\r\n")
                handle.write(f'"{python_executable}" %*\r\n')
        else:
            shim_path = (build_dir / "build_python").resolve()
            python_executable = Path(os.path.abspath(python_executable)).as_posix()
            with shim_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write("#!/bin/sh\n")
                handle.write(f'exec "{python_executable}" "$@"\n')
            shim_path.chmod(0o755)
        return shim_path

    def run(self):
        self.build_meson_modules()
        super().run()

    def build_meson_modules(self):
        only_filter = _parse_build_only_filter()
        for module in self._discover_meson_modules():
            if only_filter is not None and module["name"] not in only_filter:
                continue
            self.build_meson_module(module)

    def _discover_meson_modules(self):
        pkg_root = Path("src") / "skybornplot"
        modules = []
        for meson_file in sorted(pkg_root.rglob("meson.build")):
            rel_dir = meson_file.parent.relative_to(pkg_root)
            name = ".".join(rel_dir.parts) if rel_dir.parts else "skybornplot"
            modules.append({"name": name, "path": meson_file.parent})
        return modules

    def build_meson_module(self, module):
        module_path = module["path"]
        build_dir = module_path / "build"
        clean_requested = os.environ.get("SKYBORN_CLEAN_BUILD") == "1"
        can_reuse = (
            bool(self.inplace)
            and not clean_requested
            and (build_dir / "build.ninja").exists()
        )

        env = os.environ.copy()
        build_dir_path = str(build_dir.resolve())
        current_path = env.get("PATH", "")
        path_sep = ";" if os.name == "nt" else ":"
        env["PATH"] = (
            f"{build_dir_path}{path_sep}{current_path}"
            if current_path
            else build_dir_path
        )

        if not can_reuse:
            if build_dir.exists():
                shutil.rmtree(build_dir)
            build_dir.mkdir(parents=True, exist_ok=True)
            native_file = self._write_meson_native_file(build_dir)
            self._write_build_python_shim(build_dir)

            setup_cmd = self._meson_command(
                "setup",
                "build",
                ".",
                "--buildtype=release",
                "--native-file",
                str(native_file),
            )
            setup_cmd.append("-Db_lto=true" if self.inplace else "-Db_lto=false")

            if not self.inplace and getattr(self, "build_lib", None):
                build_lib_path = Path(self.build_lib).resolve()
                setup_cmd.extend(
                    [
                        f"--python.purelibdir={build_lib_path}",
                        f"--python.platlibdir={build_lib_path}",
                    ]
                )
            subprocess.run(setup_cmd, cwd=str(module_path), check=True, env=env)

        build_cmd = self._meson_command("compile", "-C", "build")
        subprocess.run(build_cmd, cwd=str(module_path), check=True, env=env)

        if not self.inplace and getattr(self, "build_lib", None):
            install_cmd = self._meson_command("install", "-C", "build", "--only-changed")
            subprocess.run(install_cmd, cwd=str(module_path), check=True, env=env)


class CustomDevelop(develop):
    def run(self):
        self.run_command("build_ext")
        super().run()


class CustomInstall(install):
    def run(self):
        self.run_command("build_ext")
        super().run()


class CustomInstallLib(install_lib):
    """Prune transient build artifacts and bytecode from installed package trees."""

    _PRUNE_DIR_NAMES = {
        "__pycache__",
        "build",
        "build_local",
        "meson-private",
        "meson-logs",
        "meson-info",
    }

    def run(self):
        super().run()
        package_root = Path(self.install_dir) / "skybornplot"
        if not package_root.exists():
            return
        for path in sorted(
            package_root.rglob("*"), key=lambda item: len(item.parts), reverse=True
        ):
            if path.is_dir() and (
                path.name in self._PRUNE_DIR_NAMES or path.name.startswith("build_")
            ):
                shutil.rmtree(path, ignore_errors=True)
            elif path.is_file() and path.suffix.lower() in {".pyc", ".pyo"}:
                path.unlink()


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


class CustomBdistWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure = False


if __name__ == "__main__":
    setup(
        cmdclass={
            "bdist_wheel": CustomBdistWheel,
            "build_ext": MesonBuildExt,
            "develop": CustomDevelop,
            "install": CustomInstall,
            "install_lib": CustomInstallLib,
        },
        distclass=BinaryDistribution,
        ext_modules=[],
    )
