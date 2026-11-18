// XNet inference driver: reads a raw NCHW float32 input, runs a model, and
// dumps the output tensor(s) as raw float32 plus a JSON sidecar.
//
// usage: xnet_infer.exe <model.xnet> <input.bin> <out_dir> [kind]
//   kind: 11 (fp32, default) or 10 (fp16)
//
// ASCII-only source: MSVC reads BOM-less files as the active codepage.
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <windows.h>

#include "xnet_capi.h"

static std::string toNarrow(const wchar_t *w) {
    int len = WideCharToMultiByte(CP_ACP, 0, w, -1, nullptr, 0, nullptr, nullptr);
    std::string s(len - 1, '\0');
    WideCharToMultiByte(CP_ACP, 0, w, -1, &s[0], len, nullptr, nullptr);
    return s;
}

static std::wstring toWide(const std::string &s) {
    int len = MultiByteToWideChar(CP_ACP, 0, s.c_str(), -1, nullptr, 0);
    std::wstring w(len - 1, L'\0');
    MultiByteToWideChar(CP_ACP, 0, s.c_str(), -1, &w[0], len);
    return w;
}

struct Info {
    uint64_t rank;
    int64_t dims[8];
    int kind;
};

static Info readInfo(XNetTensor t) {
    Info i = {};
    unsigned char *p = (unsigned char *)t;
    i.rank = *(uint64_t *)(p + 0x08);
    for (uint64_t k = 0; k < i.rank && k < 8; ++k)
        i.dims[k] = *(int64_t *)(p + 0x10 + k * 8);
    i.kind = *(int *)(p + 0x50);
    return i;
}

// Tensor data pointer: the storage block pointer sits at +0x60 with a leading
// offset, observed from the runtime object layout. Resolve through Lock().
__declspec(noinline) static DWORD SafeRun(XNetSession s, int blocking) {
    __try { return (DWORD)XNetDnnSessionCpuRun(s, blocking); }
    __except (EXCEPTION_EXECUTE_HANDLER) { return GetExceptionCode(); }
}

static int writeJson(const std::string &path, const char *name, const Info &i,
                     uint64_t bytes) {
    FILE *f = nullptr;
    if (fopen_s(&f, path.c_str(), "wb") != 0 || !f) return -1;
    fprintf(f, "{\"name\":\"%s\",\"rank\":%llu,\"kind\":%d,\"dims\":[",
            name, (unsigned long long)i.rank, i.kind);
    for (uint64_t k = 0; k < i.rank && k < 8; ++k)
        fprintf(f, "%s%lld", k ? "," : "", (long long)i.dims[k]);
    fprintf(f, "],\"bytes\":%llu}\n", (unsigned long long)bytes);
    fclose(f);
    return 0;
}

int wmain(int argc, wchar_t **wargv) {
    if (argc < 4) {
        std::printf("usage: xnet_infer <model.xnet> <input.bin> <out_dir> [kind]\n");
        return 2;
    }
    std::string modelPath = toNarrow(wargv[1]);
    std::string inPath = toNarrow(wargv[2]);
    std::string outDir = toNarrow(wargv[3]);
    int kind = (argc >= 5) ? _wtoi(wargv[4]) : XNET_KIND_FP32;

    HMODULE lib = LoadLibraryExW(
        L"C:\\Program Files (x86)\\Tencent\\Weixin\\4.1.13.48\\XNet.dll",
        nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!lib) { std::printf("XNet.dll load failed: %lu\n", GetLastError()); return 3; }

    // Read input header: first 4 bytes = rank, then rank * 8 bytes of int64 dims.
    FILE *in = nullptr;
    if (fopen_s(&in, inPath.c_str(), "rb") != 0 || !in) {
        std::printf("cannot open input: %s\n", inPath.c_str());
        return 4;
    }
    uint64_t rank = 0;
    if (fread(&rank, sizeof(rank), 1, in) != 1 || rank == 0 || rank > 8) {
        std::printf("bad input header (rank=%llu)\n", (unsigned long long)rank);
        fclose(in);
        return 4;
    }
    std::vector<int64_t> dims(rank, 0);
    if (fread(dims.data(), sizeof(int64_t), rank, in) != rank) {
        std::printf("truncated input header\n");
        fclose(in);
        return 4;
    }
    // dims are stored as N,C,H,W; the H,W entries are used for the tensor.
    int64_t shape[8] = {0};
    for (uint64_t i = 0; i < rank; ++i) shape[i] = dims[i];
    uint64_t total = 1;
    for (uint64_t i = 0; i < rank; ++i) total *= (uint64_t)dims[i];
    std::vector<float> buffer(total, 0.0f);
    size_t got = fread(buffer.data(), sizeof(float), total, in);
    fclose(in);
    if (got != total) {
        std::printf("input truncated: got %llu of %llu floats\n",
                    (unsigned long long)got, (unsigned long long)total);
        return 4;
    }

    XNetModel model = XNetDnnModelCpuCreateFromFile(modelPath.c_str(), nullptr);
    if (!model) { std::printf("model load failed\n"); return 5; }
    XNetSession session = XNetDnnSessionCpuCreate(model);
    if (!session) { std::printf("session create failed\n"); return 6; }
    if (XNetDnnSessionCpuInitializeInputs(session) != 0) {
        std::printf("InitializeInputs failed\n");
        return 7;
    }

    XNetTensor input = XNetDnnTensorCpuCreate(rank, shape, kind);
    if (!input) { std::printf("input tensor create failed\n"); return 8; }
    void *ptr = XNetDnnTensorCpuLock(input);
    if (!ptr) { std::printf("input tensor lock failed\n"); return 8; }
    uint64_t tensorBytes = XNetDnnTensorCpuGetSizeInBytes(input);
    size_t copyCount = (size_t)(tensorBytes / sizeof(float));
    if (copyCount > buffer.size()) copyCount = buffer.size();
    std::memcpy(ptr, buffer.data(), copyCount * sizeof(float));
    XNetDnnTensorCpuUnLock(input);

    const char *inName = XNetDnnModelCpuGetInputName(model, 0);
    int rc = XNetDnnSessionCpuSetInput(session, inName, input);
    if (rc != 0) { std::printf("SetInput failed: %d\n", rc); return 9; }

    DWORD runRc = SafeRun(session, 0);
    if (runRc != 0) { std::printf("Run failed: 0x%08lX\n", runRc); return 10; }

    uint64_t no = XNetDnnModelCpuGetNumOutputs(model);
    std::string manifest = outDir + "\\outputs.json";
    FILE *mf = nullptr;
    if (fopen_s(&mf, manifest.c_str(), "wb") != 0 || !mf) {
        std::printf("cannot write manifest\n");
        return 11;
    }
    fprintf(mf, "{\"outputs\":[\n");
    for (uint64_t i = 0; i < no; ++i) {
        const char *name = XNetDnnModelCpuGetOutputName(model, i);
        if (!name) name = "output";
        XNetTensor out = XNetDnnSessionCpuGetOutput(session, name);
        if (!out) { std::printf("output '%s' not ready\n", name); continue; }
        Info oi = readInfo(out);
        void *op = XNetDnnTensorCpuLock(out);
        if (!op) { std::printf("output '%s' lock failed\n", name); continue; }
        uint64_t count = 1;
        for (uint64_t k = 0; k < oi.rank && k < 8; ++k) count *= (uint64_t)oi.dims[k];
        std::string binPath = outDir + "\\" + std::string(name) + ".bin";
        FILE *bf = nullptr;
        if (fopen_s(&bf, binPath.c_str(), "wb") == 0 && bf) {
            fwrite(op, sizeof(float), (size_t)count, bf);
            fclose(bf);
        }
        std::string metaPath = outDir + "\\" + std::string(name) + ".json";
        writeJson(metaPath, name, oi, count * sizeof(float));
        fprintf(mf, "  {\"name\":\"%s\",\"file\":\"%s.bin\",\"meta\":\"%s.json\"}%s\n",
                name, name, name, (i + 1 < no) ? "," : "");
        std::printf("output '%s' rank=%llu kind=%d count=%llu\n",
                    name, (unsigned long long)oi.rank, oi.kind, (unsigned long long)count);
        XNetDnnTensorCpuUnLock(out);
    }
    fprintf(mf, "]}\n");
    fclose(mf);

    XNetDnnTensorCpuDestroy(input);
    XNetDnnSessionCpuDestroy(session);
    XNetDnnModelCpuDestroy(model);
    std::printf("inference ok\n");
    return 0;
}
