"""Builds kem_bench, the C driver shared by the timing harness
(bench/computational/api/) and the memory harness (bench/memory/), and
holds the list of parameter sets both of them measure.

Everything is built under bench/driver/build/ (gitignored):

    liboqs-native/     the liboqs submodule, OQS_OPT_TARGET=auto (AVX2 here)
    liboqs-generic/    the same, OQS_OPT_TARGET=generic (portable C)
    liboqs-icicle/     native, with ML-KEM on the GPU (OQS_USE_ICICLE=ON)
    icicle-{src,build,install}/   ICICLE at a pinned commit, for liboqs-icicle
    openssl-<ver>/     a pinned OpenSSL release, checked by SHA-256
    kem_bench-<variant>   timing build
    kem_mem-<variant>     memory build: -DKEM_MEMORY, allocator wrapped
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent            # bench/driver
REPO = HERE.parent.parent
BUILD = HERE / "build"
ALGORITHMS_MD = REPO / "bench" / "algorithms.md"

# ---------- what to measure ----------

# The sets in bench/algorithms.md. check_list() fails if they drift apart.
LIBOQS_ALGS = [
    "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
    "Classic-McEliece-348864", "Classic-McEliece-348864f",
    "Classic-McEliece-460896", "Classic-McEliece-460896f",
    "Classic-McEliece-6688128", "Classic-McEliece-6688128f",
    "Classic-McEliece-6960119", "Classic-McEliece-6960119f",
    "Classic-McEliece-8192128", "Classic-McEliece-8192128f",
    "NTRU-HPS-2048-509", "NTRU-HPS-2048-677", "NTRU-HPS-4096-821",
    "NTRU-HPS-4096-1229", "NTRU-HRSS-701", "NTRU-HRSS-1373",
]
# The classical baselines, plus ML-KEM a second time as the same-library
# comparison.
OPENSSL_ALGS = [
    "X25519", "P-256", "RSA-2048", "RSA-3072", "ffdhe2048", "ffdhe3072",
    "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
]
OPS = ("keygen", "encaps", "decaps")


def all_combos() -> list[tuple[str, str]]:
    """Every (implementation, set) pair, liboqs first."""
    return [("liboqs", alg) for alg in LIBOQS_ALGS] + [("openssl", alg) for alg in OPENSSL_ALGS]


def listed_sets() -> set[str]:
    """First cell of every row in a `| Set | ...` table of algorithms.md."""
    names, in_table = set(), False
    for line in ALGORITHMS_MD.read_text().splitlines():
        if line.startswith("| Set "):
            in_table = True
        elif in_table and line.startswith("|"):
            cell = line.split("|")[1].strip()
            if not cell.startswith("---"):
                names.add(cell)
        else:
            in_table = False
    return names


def check_list() -> None:
    listed, ours = listed_sets(), set(LIBOQS_ALGS) | set(OPENSSL_ALGS)
    if listed != ours:
        sys.exit("ERROR: bench/driver/kem_build.py and bench/algorithms.md disagree.\n"
                 f"  only in algorithms.md: {sorted(listed - ours)}\n"
                 f"  only in kem_build.py:  {sorted(ours - listed)}")


# ---------- liboqs ----------

LIBOQS_SRC = REPO / "implementations" / "liboqs"
LIBOQS_OPTIONS = {
    "CMAKE_BUILD_TYPE": "Release",
    "OQS_USE_OPENSSL": "OFF",   # liboqs uses its own RNG and hashes
    "OQS_DIST_BUILD": "OFF",    # one implementation per entry point, no runtime dispatch
    "OQS_BUILD_ONLY_LIB": "ON",
}
# variant -> OQS_OPT_TARGET
VARIANTS = {"native": "auto", "generic": "generic"}
# GPU builds: native, with liboqs' ML-KEM entry points moved onto the GPU.
# Kept out of VARIANTS so the memory harness's "both" stays the CPU builds.
GPU_VARIANTS = {"icicle": {"OQS_OPT_TARGET": "auto", "OQS_USE_ICICLE": "ON"}}


def liboqs_dir(variant: str) -> Path:
    return BUILD / f"liboqs-{variant}"


def liboqs_options(variant: str) -> dict[str, str]:
    if variant in GPU_VARIANTS:
        return {**LIBOQS_OPTIONS, **GPU_VARIANTS[variant]}
    return {**LIBOQS_OPTIONS, "OQS_OPT_TARGET": VARIANTS[variant]}


def liboqs_revision() -> str:
    return output_of(["git", "-C", str(LIBOQS_SRC), "describe", "--tags", "--always"])


def build_liboqs(variant: str) -> None:
    out = liboqs_dir(variant)
    paths = {}
    if variant == "icicle":
        build_icicle()
        paths = {"CMAKE_PREFIX_PATH": ICICLE_PREFIX, "Taskflow_DIR": TASKFLOW_STUB,
                 "CMAKE_CUDA_COMPILER": NVCC}
    if not (out / "CMakeCache.txt").exists():
        log(f"[build] configuring liboqs ({variant})")
        run(["cmake", "-S", str(LIBOQS_SRC), "-B", str(out), "-G", "Ninja",
             *(f"-D{k}={v}" for k, v in {**liboqs_options(variant), **paths}.items())],
            stdout=subprocess.DEVNULL)
    log(f"[build] liboqs ({variant})")
    run(["cmake", "--build", str(out), "--target", "oqs"], stdout=subprocess.DEVNULL)


# ---------- ICICLE (GPU ML-KEM for liboqs-icicle) ----------

ICICLE_REPO = "https://github.com/ingonyama-zk/icicle.git"
ICICLE_COMMIT = "625532a624e5aaa6e9d31a1c92587f1fcc30dc76"   # main, 2025-08-06
ICICLE_SRC = BUILD / "icicle-src"
ICICLE_BUILD = BUILD / "icicle-build"
ICICLE_PREFIX = BUILD / "icicle-install"
# The recipe in liboqs' CONFIGURE.md (OQS_USE_ICICLE). The CUDA
# architecture is left to ICICLE, which compiles for the local GPU.
ICICLE_OPTIONS = {
    "CMAKE_BUILD_TYPE": "Release",
    "CPU_BACKEND": "OFF",
    "DISABLE_ALL_FEATURES": "ON",
    "PQC": "ON",
    "CUDA_PQC_BACKEND": "ON",
    "ICICLE_STATIC_LINK": "ON",
    "PQC_PACKAGE": "ON",
}
CUDA_HOME = Path(os.environ.get("CUDA_HOME", "/usr/local/cuda"))
NVCC = CUDA_HOME / "bin" / "nvcc"
# icicle_pqc_packageConfig.cmake calls find_dependency(Taskflow), which
# fails when Taskflow is absent, but no ICICLE target uses it. An empty
# config file satisfies the call.
TASKFLOW_STUB = BUILD / "stubs" / "taskflow"
# Whole-archive, because ICICLE's backend registers itself from static
# initialisers that nothing else references.
ICICLE_LIBS = [ICICLE_PREFIX / "lib" / f"lib{name}.a"
               for name in ("icicle_device", "icicle_pqc", "icicle_backend_cuda_pqc")]
ICICLE_LINK = ["-Wl,--whole-archive", *map(str, ICICLE_LIBS), "-Wl,--no-whole-archive",
               f"-L{CUDA_HOME / 'lib64'}", f"-Wl,-rpath,{CUDA_HOME / 'lib64'}",
               "-lcudart", "-lstdc++", "-lm"]


def icicle_revision() -> str:
    return output_of(["git", "-C", str(ICICLE_SRC), "rev-parse", "HEAD"])


def build_icicle() -> None:
    TASKFLOW_STUB.mkdir(parents=True, exist_ok=True)
    (TASKFLOW_STUB / "TaskflowConfig.cmake").write_text(
        "# Empty stub; see TASKFLOW_STUB in bench/driver/kem_build.py.\n")
    if all(p.exists() for p in ICICLE_LIBS):
        return
    if not NVCC.exists():
        sys.exit(f"ERROR: {NVCC} not found; install the CUDA toolkit or set CUDA_HOME")
    if not ICICLE_SRC.exists():
        log(f"[build] cloning {ICICLE_REPO}")
        run(["git", "clone", "-q", ICICLE_REPO, str(ICICLE_SRC)])
    run(["git", "-C", str(ICICLE_SRC), "checkout", "-q", ICICLE_COMMIT])
    log("[build] ICICLE (several minutes)")
    run(["cmake", "-S", str(ICICLE_SRC / "icicle"), "-B", str(ICICLE_BUILD), "-G", "Ninja",
         f"-DCMAKE_INSTALL_PREFIX={ICICLE_PREFIX}", f"-DCMAKE_CUDA_COMPILER={NVCC}",
         *(f"-D{k}={v}" for k, v in ICICLE_OPTIONS.items())],
        stdout=subprocess.DEVNULL)
    run(["cmake", "--build", str(ICICLE_BUILD)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(["cmake", "--install", str(ICICLE_BUILD)], stdout=subprocess.DEVNULL)


# ---------- OpenSSL ----------

OPENSSL_VERSION = "3.5.9"
OPENSSL_SHA256 = "603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a"
OPENSSL_URL = (f"https://github.com/openssl/openssl/releases/download/"
               f"openssl-{OPENSSL_VERSION}/openssl-{OPENSSL_VERSION}.tar.gz")
OPENSSL_DIR = BUILD / f"openssl-{OPENSSL_VERSION}"
OPENSSL_PREFIX = OPENSSL_DIR / "install"
OPENSSL_CONFIGURE = ["no-shared", "no-tests"]
LIBCRYPTO = OPENSSL_PREFIX / "lib" / "libcrypto.a"


def fetch_openssl_source() -> Path:
    """Download (once) and verify the pinned tarball; return the source dir."""
    OPENSSL_DIR.mkdir(parents=True, exist_ok=True)
    tarball = OPENSSL_DIR / f"openssl-{OPENSSL_VERSION}.tar.gz"
    if not tarball.exists():
        log(f"[build] downloading {OPENSSL_URL}")
        urllib.request.urlretrieve(OPENSSL_URL, tarball)

    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    if digest != OPENSSL_SHA256:
        tarball.unlink()
        sys.exit(f"ERROR: OpenSSL tarball SHA-256 {digest} != pinned {OPENSSL_SHA256}")

    src = OPENSSL_DIR / f"openssl-{OPENSSL_VERSION}"
    if not src.exists():
        with tarfile.open(tarball) as t:
            t.extractall(OPENSSL_DIR, filter="data")
    return src


def build_openssl() -> None:
    if LIBCRYPTO.exists():
        return
    src = fetch_openssl_source()
    log(f"[build] OpenSSL {OPENSSL_VERSION} (several minutes)")
    run(["./Configure", f"--prefix={OPENSSL_PREFIX}", "--libdir=lib", *OPENSSL_CONFIGURE],
        cwd=src, stdout=subprocess.DEVNULL)
    run(["make", f"-j{os.cpu_count() or 4}"], cwd=src, stdout=subprocess.DEVNULL)
    run(["make", "install_sw"], cwd=src, stdout=subprocess.DEVNULL)


# ---------- the driver ----------

DRIVER_SRC = HERE / "kem_bench.c"
DRIVER_CFLAGS = ["-O2", "-march=native", "-Wall", "-Wextra"]
# Route every allocation from the driver, liboqs.a and libcrypto.a
# through the tracking wrappers in kem_bench.c.
MEMORY_WRAP_FLAGS = [f"-Wl,--wrap={f}" for f in
                     ("malloc", "calloc", "realloc", "free", "aligned_alloc", "posix_memalign", "memalign")]


def driver_path(variant: str, memory: bool = False) -> Path:
    return BUILD / f"{'kem_mem' if memory else 'kem_bench'}-{variant}"


def build_driver(variant: str, memory: bool = False) -> Path:
    exe = driver_path(variant, memory)
    liboqs = liboqs_dir(variant)
    libs = [liboqs / "lib" / "liboqs.a", LIBCRYPTO]
    newest_input = max(p.stat().st_mtime for p in [DRIVER_SRC, *libs])
    if exe.exists() and exe.stat().st_mtime >= newest_input:
        return exe
    log(f"[build] {exe.name}")
    extra = ["-DKEM_MEMORY", *MEMORY_WRAP_FLAGS] if memory else []
    gpu = ICICLE_LINK if variant == "icicle" else []
    run(["cc", *DRIVER_CFLAGS, *extra, "-o", str(exe), str(DRIVER_SRC),
         f"-I{liboqs / 'include'}", f"-I{OPENSSL_PREFIX / 'include'}",
         *map(str, libs), *gpu, "-ldl", "-pthread"])
    return exe


def build_all(variants: list[str], memory: bool = False) -> dict[str, Path]:
    """Check the algorithm list and build everything; return variant ->
    driver (the memory build if memory=True)."""
    check_list()
    build_openssl()
    drivers = {}
    for v in variants:
        build_liboqs(v)
        drivers[v] = build_driver(v, memory)
    return drivers


def build_description(variants: list[str]) -> dict:
    """What was built, for env.json."""
    gpu = {}
    if "icicle" in variants:
        gpu = {"icicle_revision": icicle_revision(), "icicle_options": ICICLE_OPTIONS,
               "nvcc": output_of([str(NVCC), "--version"]).splitlines()[-1],
               "gpu": output_of(["nvidia-smi", "--query-gpu=name,driver_version,compute_cap",
                                 "--format=csv,noheader"])}
    return {
        "liboqs_revision": liboqs_revision(),
        "liboqs_options": {v: liboqs_options(v) for v in variants},
        **gpu,
        "openssl_source": {"version": OPENSSL_VERSION, "sha256": OPENSSL_SHA256,
                           "configure": OPENSSL_CONFIGURE},
        "driver_cflags": DRIVER_CFLAGS,
    }


# ---------- helpers ----------

def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def output_of(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
