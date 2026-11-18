// Final end-to-end XNet OCR inference demo.
// Loads the det model, runs one image-sized input, reads score_map back and
// reports statistics, proving the generated XNet.lib drives the model.
// usage: xnet_ocr_demo <model.xnet> <height> <width>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <algorithm>
#include <functional>
#include <windows.h>

#include "xnet_capi.h"

static std::string toNarrow(const wchar_t *w) {
    int len = WideCharToMultiByte(CP_ACP, 0, w, -1, nullptr, 0, nullptr, nullptr);
    std::string s(len - 1, '\0');
    WideCharToMultiByte(CP_ACP, 0, w, -1, &s[0], len, nullptr, nullptr);
    return s;
}

// Output tensors from GetOutput carry zeroed layout fields, which makes the
// accessor helpers read out of bounds. Read shape/kind from the object itself.
struct TensorInfo {
    uint64_t rank;
    int64_t  dims[8];
    int      kind;
};

static TensorInfo readTensorInfo(XNetTensor t) {
    TensorInfo info = {};
    unsigned char *p = (unsigned char *)t;
    info.rank = *(uint64_t *)(p + 0x08);
    for (uint64_t i = 0; i < info.rank && i < 8; ++i)
        info.dims[i] = *(int64_t *)(p + 0x10 + i * 8);
    info.kind = *(int *)(p + 0x50);
    return info;
}

static void printInfo(const char *tag, const TensorInfo &i) {
    std::printf("  %-12s rank=%llu kind=%d dims=[", tag,
                (unsigned long long)i.rank, i.kind);
    for (uint64_t k = 0; k < i.rank && k < 8; ++k)
        std::printf("%s%lld", k ? "," : "", (long long)i.dims[k]);
    std::printf("]\n");
}

// SEH wrapper in a noinline function: __try cannot coexist with C++ unwinding.
__declspec(noinline) static DWORD SafeRun(XNetSession s, int blocking) {
    __try { return (DWORD)XNetDnnSessionCpuRun(s, blocking); }
    __except (EXCEPTION_EXECUTE_HANDLER) { return GetExceptionCode(); }
}

// Try "<root>\<version>\XNet.dll" for every version-looking subdirectory,
// newest first, then "<root>\XNet.dll" itself.
static HMODULE tryVersionDir(const wchar_t *root) {
    wchar_t pattern[1024];
    _snwprintf_s(pattern, _countof(pattern), _TRUNCATE, L"%s\\*", root);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return nullptr;

    std::vector<std::wstring> versions;
    do {
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        // A version folder looks like "4.1.13.48" (at least two dots).
        int dots = 0;
        for (const wchar_t *p = fd.cFileName; *p; ++p)
            if (*p == L'.') ++dots;
        if (dots >= 2) versions.push_back(fd.cFileName);
    } while (FindNextFileW(h, &fd));
    FindClose(h);

    std::sort(versions.begin(), versions.end(), std::greater<std::wstring>());
    for (const std::wstring &v : versions) {
        wchar_t path[1024];
        _snwprintf_s(path, _countof(path), _TRUNCATE, L"%s\\%s\\XNet.dll",
                     root, v.c_str());
        HMODULE lib = LoadLibraryExW(path, nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (lib) { std::printf("      source: %s\\%s\n", toNarrow(root).c_str(),
                               toNarrow(v.c_str()).c_str()); return lib; }
    }

    wchar_t direct[1024];
    _snwprintf_s(direct, _countof(direct), _TRUNCATE, L"%s\\XNet.dll", root);
    HMODULE lib = LoadLibraryExW(direct, nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (lib) { std::printf("      source: %s\n", toNarrow(root).c_str()); }
    return lib;
}

// Search XNet.dll the same way ocr\paths.py does: an explicit override first,
// then the bundled copy, then the newest Weixin version subdirectory. A fixed
// install path would break on any other machine or WeChat version.
static HMODULE loadXNetDll(const wchar_t *exeDir) {
    const wchar_t *override = _wgetenv(L"XNET_WEIXIN_DIR");
    if (override && *override) {
        wchar_t path[1024];
        _snwprintf_s(path, _countof(path), _TRUNCATE, L"%s\\XNet.dll", override);
        HMODULE lib = LoadLibraryExW(path, nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (lib) { std::printf("      source: XNET_WEIXIN_DIR\n"); return lib; }
    }
    if (exeDir && *exeDir) {
        wchar_t path[1024];
        _snwprintf_s(path, _countof(path), _TRUNCATE, L"%s\\XNet.dll", exeDir);
        HMODULE lib = LoadLibraryExW(path, nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (lib) { std::printf("      source: bundled next to exe\n"); return lib; }
    }

    static const wchar_t *roots[] = {
        L"C:\\Program Files (x86)\\Tencent\\Weixin",
        L"C:\\Program Files\\Tencent\\Weixin",
    };
    static const wchar_t *localRoot = nullptr;
    if (!localRoot) {
        // LOCALAPPDATA is resolved once; it is stable for the process lifetime.
        static wchar_t buf[MAX_PATH];
        if (GetEnvironmentVariableW(L"LOCALAPPDATA", buf, MAX_PATH))
            localRoot = buf;
    }
    for (int r = 0; r < 2; ++r) {
        if (!roots[r]) continue;
        HMODULE lib = tryVersionDir(roots[r]);
        if (lib) return lib;
    }
    if (localRoot) {
        wchar_t path[1024];
        _snwprintf_s(path, _countof(path), _TRUNCATE,
                     L"%s\\Tencent\\Weixin", localRoot);
        HMODULE lib = tryVersionDir(path);
        if (lib) return lib;
    }
    std::printf("      source: none found\n");
    return nullptr;
}

int wmain(int argc, wchar_t **wargv) {
    if (argc < 4) { std::printf("usage: xnet_ocr_demo <model.xnet> <h> <w>\n"); return 2; }
    std::string modelPath = toNarrow(wargv[1]);
    int h = _wtoi(wargv[2]);
    int w = _wtoi(wargv[3]);

    wchar_t exeDir[MAX_PATH] = {};
    GetModuleFileNameW(nullptr, exeDir, MAX_PATH);
    if (wcsrchr(exeDir, L'\\')) *wcsrchr(exeDir, L'\\') = L'\0';

    HMODULE lib = loadXNetDll(exeDir);
    if (!lib) {
        std::printf("XNet.dll load failed: %lu\n", GetLastError());
        std::printf("set XNET_WEIXIN_DIR to the directory holding XNet.dll\n");
        return 3;
    }
    std::printf("[1] XNet.dll loaded (via XNet.lib import table)\n");

    XNetModel model = XNetDnnModelCpuCreateFromFile(modelPath.c_str(), nullptr);
    if (!model) { std::printf("model load failed\n"); return 4; }
    std::printf("[2] model loaded: %p  inputs=%llu outputs=%llu\n", (void *)model,
                (unsigned long long)XNetDnnModelCpuGetNumInputs(model),
                (unsigned long long)XNetDnnModelCpuGetNumOutputs(model));

    XNetSession session = XNetDnnSessionCpuCreate(model);
    if (!session) { std::printf("session create failed\n"); return 5; }
    std::printf("[3] session created: %p\n", (void *)session);

    if (XNetDnnSessionCpuInitializeInputs(session) != 0) {
        std::printf("InitializeInputs failed\n"); return 6;
    }
    std::printf("[4] inputs initialized\n");

    int64_t shape[4] = {1, 3, (int64_t)h, (int64_t)w};
    XNetTensor input = XNetDnnTensorCpuCreate(4, shape, XNET_KIND_FP32);
    if (!input) { std::printf("tensor create failed\n"); return 7; }
    void *ptr = XNetDnnTensorCpuLock(input);
    if (!ptr) { std::printf("tensor lock failed\n"); return 8; }
    uint64_t n = XNetDnnTensorCpuGetSizeInBytes(input) / sizeof(float);
    float *pixels = (float *)ptr;
    // Smooth gradient instead of a flat fill: gives the detector real structure.
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            float v = (float)((x * 255) / (w > 1 ? w - 1 : 1));
            for (int c = 0; c < 3; ++c) {
                size_t idx = ((size_t)c * h + y) * w + x;
                if (idx < n) pixels[idx] = v / 255.0f;
            }
        }
    }
    XNetDnnTensorCpuUnLock(input);
    std::printf("[5] input tensor filled (%llu floats)\n", (unsigned long long)n);

    if (XNetDnnSessionCpuSetInput(session, "input", input) != 0) {
        std::printf("SetInput failed\n"); return 9;
    }
    std::printf("[6] input bound\n");

    DWORD runRc = SafeRun(session, 0); // non-blocking
    if (runRc != 0) { std::printf("Run failed: 0x%08lX\n", runRc); return 10; }
    std::printf("[7] inference run returned 0\n");

    const char *outs[3] = {"score_map", "kernel_map", "ori_map"};
    XNetTensor scoreMap = nullptr;
    for (int i = 0; i < 3; ++i) {
        XNetTensor t = XNetDnnSessionCpuGetOutput(session, outs[i]);
        std::printf("[8] output '%s' -> %p\n", outs[i], (void *)t);
        if (t) {
            printInfo(outs[i], readTensorInfo(t));
            if (i == 0) scoreMap = t;
        }
    }

    if (scoreMap) {
        void *sp = XNetDnnTensorCpuLock(scoreMap);
        if (sp) {
            const float *f = (const float *)sp;
            uint64_t count = (uint64_t)readTensorInfo(scoreMap).dims[1] *
                             readTensorInfo(scoreMap).dims[2];
            double sum = 0.0, maxv = -1e30, minv = 1e30;
            uint64_t positive = 0;
            for (uint64_t i = 0; i < count; ++i) {
                double v = f[i];
                sum += v;
                if (v > maxv) maxv = v;
                if (v < minv) minv = v;
                if (v > 0.5) ++positive;
            }
            std::printf("[9] score_map stats: count=%llu mean=%.6f min=%.6f max=%.6f above0.5=%llu\n",
                        (unsigned long long)count, count ? sum / count : 0.0,
                        minv, maxv, (unsigned long long)positive);
            XNetDnnTensorCpuUnLock(scoreMap);
        }
    }

    std::printf("[OK] model executed end to end through XNet.lib\n");
    return 0;
}
