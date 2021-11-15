from functools import lru_cache
import logging
from pathlib import Path
from typing import IO, Iterator, Optional, Tuple, Union

from datalad.support.annexrepo import AnnexRepo
from datalad.utils import get_dataset_root
import fsspec
from fsspec.implementations.cached import CachingFileSystem

lgr = logging.getLogger("datalad_fuse.fsspec")


class FsspecAdapter:
    def __init__(self, path: Union[str, Path]) -> None:
        self.root = Path(path)
        self.annexes = {}
        self.cache_dir = Path(path, ".git", "datalad", "cache", "fsspec")
        self.fs = CachingFileSystem(
            fs=fsspec.filesystem("http"),
            # target_protocol='blockcache',
            cache_storage=str(self.cache_dir),
            # cache_check=600,
            # block_size=1024,
            # check_files=True,
            # expiry_times=True,
            # same_names=True
        )

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        for annex in self.annexes.values():
            annex._batched.clear()
        self.annexes.clear()

    @lru_cache(maxsize=128)
    def get_dataset_path(self, path: Union[str, Path]) -> Path:
        path = Path(self.root, path)
        dspath = get_dataset_root(path)
        if dspath is None:
            raise ValueError(f"Path not under DataLad: {path}")
        dspath = Path(dspath)
        try:
            dspath.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Path not under root dataset: {path}")
        return dspath

    def annexize(self, filepath: Union[str, Path]) -> Tuple[AnnexRepo, str]:
        dspath = self.get_dataset_path(filepath)
        try:
            annex = self.annexes[dspath]
        except KeyError:
            annex = self.annexes[dspath] = AnnexRepo(dspath)
        relpath = str(Path(filepath).relative_to(dspath))
        return annex, relpath

    def get_urls(self, annex: AnnexRepo, filepath: Union[str, Path]) -> Iterator[str]:
        whereis = annex.whereis(str(filepath), output="full", batch=True)
        remote_uuids = []
        for ru, v in whereis.items():
            remote_uuids.append(ru)
            for u in v["urls"]:
                if is_http_url(u):
                    yield u

        key = annex.get_file_key(filepath, batch=True)
        path_mixed = annex._batched.get(
            "examinekey",
            annex_options=["--format=annex/objects/${hashdirmixed}${key}/${key}\\n"],
            path=annex.path,
        )(key)
        path_lower = annex._batched.get(
            "examinekey",
            annex_options=["--format=annex/objects/${hashdirlower}${key}/${key}\\n"],
            path=annex.path,
        )(key)

        uuid2remote_url = {}
        for r in annex.get_remotes():
            ru = annex.config.get(f"remote.{r}.annex-uuid")
            if ru is None:
                continue
            remote_url = annex.config.get(f"remote.{r}.url")
            if remote_url is None:
                continue
            remote_url = annex.config.rewrite_url(remote_url)
            uuid2remote_url[ru] = remote_url

        for ru in remote_uuids:
            try:
                base_url = uuid2remote_url[ru]
            except KeyError:
                continue
            if is_http_url(base_url):
                if base_url.lower().rstrip("/").endswith("/.git"):
                    paths = [path_mixed, path_lower]
                else:
                    paths = [
                        path_lower,
                        path_mixed,
                        f".git/{path_lower}",
                        f".git/{path_mixed}",
                    ]
                for p in paths:
                    yield base_url.rstrip("/") + "/" + p

    def open(
        self,
        filepath: Union[str, Path],
        mode: str = "rb",
        encoding: str = "utf-8",
        errors: Optional[str] = None,
    ) -> IO:
        if mode not in ("r", "rb", "rt"):
            raise NotImplementedError("Only modes 'r', 'rb', and 'rt' are supported")
        if mode == "rb":
            kwargs = {}
        else:
            kwargs = {"encoding": encoding, "errors": errors}
        annex, relpath = self.annexize(filepath)
        under_annex = annex.is_under_annex(relpath, batch=True)
        if under_annex:
            has_content = annex.file_has_content(relpath, batch=True)
            lgr.debug(
                "%s: under annex, %s content",
                filepath,
                "has" if has_content else "does not have",
            )
        else:
            has_content = False
            lgr.debug("%s: not under annex", filepath)
        if under_annex and not has_content:
            lgr.debug("%s: opening via fsspec", filepath)
            for url in self.get_urls(annex, relpath):
                try:
                    lgr.debug("%s: Attempting to open via URL %s", filepath, url)
                    return self.fs.open(url, mode, **kwargs)
                except FileNotFoundError as e:
                    lgr.debug(
                        "Failed to open file %s at URL %s: %s", filepath, url, str(e)
                    )
            raise IOError(f"Could not find a usable URL for {filepath}")
        else:
            lgr.debug("%s: opening directly", filepath)
            return open(filepath, mode, **kwargs)

    def clear(self) -> None:
        self.fs.clear_cache()

    def is_under_annex(self, filepath: Union[str, Path]) -> bool:
        annex, relpath = self.annexize(filepath)
        return annex.is_under_annex(relpath, batch=True)


def is_http_url(s):
    return s.lower().startswith(("http://", "https://"))
