// XNet.dll C inference API declarations.
//
// Derived from the export table and disassembly of
//   C:\Program Files (x86)\Tencent\Weixin\4.1.13.48\XNet.dll
// Pair with XNet.lib (built from XNet.def) or resolve via GetProcAddress.
//
// Notes:
//  - All functions use __cdecl and return opaque handles (void*).
//  - XNetDnnModelCpuCreateFromFile takes (path, options); passing NULL for
//    options selects the built-in defaults and was verified to work.
//  - Model and session own their handles; release with the Destroy calls.
//
// This is a reverse-engineered interface for the locally installed Tencent
// WeChat component. It is not an official SDK and is bound to this build.

#ifndef XNET_CAPI_H
#define XNET_CAPI_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Opaque XNet object handles.
typedef void *XNetModel;
typedef void *XNetSession;
typedef void *XNetTensor;
typedef void *XNetWorkspace;

// Tensor data kinds, verified by calling XNet::GetStorageDataKindName
// (values 0..12; 0 and 1 are internal wildcard entries).
typedef enum XNetDataKind {
    XNET_KIND_INVALID = 0,
    XNET_KIND_WILDCARD = 1,
    XNET_KIND_UINT8 = 2,
    XNET_KIND_UINT16 = 3,
    XNET_KIND_UINT32 = 4,
    XNET_KIND_UINT64 = 5,
    XNET_KIND_INT8 = 6,
    XNET_KIND_INT16 = 7,
    XNET_KIND_INT32 = 8,
    XNET_KIND_INT64 = 9,
    XNET_KIND_FP16 = 10,
    XNET_KIND_FP32 = 11,
    XNET_KIND_FP64 = 12
} XNetDataKind;

// Model lifecycle.
XNetModel XNetDnnModelCpuCreateFromFile(const char *filePath, const void *options);
XNetModel XNetDnnModelCpuCreateFromStream(const void *stream, uint64_t size, const void *options);
void     XNetDnnModelCpuDestroy(XNetModel model);

uint64_t      XNetDnnModelCpuGetNumInputs(XNetModel model);
uint64_t      XNetDnnModelCpuGetNumOutputs(XNetModel model);
const char   *XNetDnnModelCpuGetInputName(XNetModel model, uint64_t index);
const char   *XNetDnnModelCpuGetOutputName(XNetModel model, uint64_t index);

// Session lifecycle.
XNetSession XNetDnnSessionCpuCreate(XNetModel model);
void        XNetDnnSessionCpuDestroy(XNetSession session);
int         XNetDnnSessionCpuInitializeInputs(XNetSession session);
int         XNetDnnSessionCpuSetInput(XNetSession session, const char *name, XNetTensor tensor);
// Non-blocking execution. Verified: blocking=1 crashes inside the engine,
// blocking=0 returns 0; outputs are then collected after the run completes.
int         XNetDnnSessionCpuRun(XNetSession session, int blocking);

// Returns a newly allocated output tensor, or NULL when the named output is
// not ready. The caller owns it and must release it with
// XNetDnnTensorCpuDestroy. Verified against the disassembly: the return value
// is the tensor pointer itself, not a status code.
XNetTensor  XNetDnnSessionCpuGetOutput(XNetSession session, const char *name);

// Tensor lifecycle. shape is an array of `rank` int64 dimensions.
XNetTensor XNetDnnTensorCpuCreate(uint64_t rank, const int64_t *shape, int dataKind);
XNetTensor XNetDnnTensorCpuCreateFromBuffer(void *buffer, uint64_t rank, const int64_t *shape, int dataKind);
void       XNetDnnTensorCpuDestroy(XNetTensor tensor);

uint64_t      XNetDnnTensorCpuGetDim(XNetTensor tensor, uint64_t axis);
uint64_t      XNetDnnTensorCpuGetShape(XNetTensor tensor, int64_t *outShape, uint64_t rank);
uint64_t      XNetDnnTensorCpuGetSizeInBytes(XNetTensor tensor);
int           XNetDnnTensorCpuGetDataKind(XNetTensor tensor);
void         *XNetDnnTensorCpuLock(XNetTensor tensor);
void          XNetDnnTensorCpuUnLock(XNetTensor tensor);

// Workspace lifecycle.
XNetWorkspace XNetDnnWorkspaceCpuCreate(uint64_t sizeInBytes);
void          XNetDnnWorkspaceCpuDestroy(XNetWorkspace workspace);

#ifdef __cplusplus
}
#endif

#endif // XNET_CAPI_H
