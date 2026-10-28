# SPDX-License-Identifier: GPL-3.0-or-later
"""A fake KiCad API server for the button's tests (Stage 2 design 5.5, 5.8): kipy's real client talks to it as to KiCad
9.0.7's, through an nng Rep0 socket that answers kipy's own protobuf messages."""
import threading
import time
from pathlib import Path

import pynng
from google.protobuf.empty_pb2 import Empty
from kipy.proto.board import board_types_pb2
from kipy.proto.common import ApiRequest, ApiResponse, ApiStatusCode
from kipy.proto.common.commands import base_commands_pb2, editor_commands_pb2
from kipy.proto.common.types import base_types_pb2
from kipy.util import pack_any

SLOW_S = 1.5  # how late a "SLOW" answer comes: past the helper's 1 s (button.TIMEOUT_MS)


class FakeKiCad:
    """KiCad's API server at `url` (ipc://...), as kipy 0.8 meets KiCad 9.0.7's. Its token is `token`: a request with
    another, non-empty one gets AS_TOKEN_MISMATCH. Its PCB editor has the board file `board` open (GetOpenDocuments:
    its folder and file name) with the pads `pads` (KIIDs) and the footprints `footprints` (references) selected
    (GetSelection); GetVersion answers `version`; RefillZones and Ping answer Empty; SaveDocument writes `save` into
    `board` when given, as KiCad's save writes the edits it holds, and answers Empty. `errors` maps a request's type
    name to what it answers first, one per request: an AS_ status name, or "SLOW", its usual answer SLOW_S late, as
    KiCad answers once its main thread is free of a zone fill or a large save. `seen` lists the requests' type names
    in order, and `tokens` the tokens they carried."""

    def __init__(self, url: str, board: Path, *, pads=(), footprints=(), version=(9, 0, 7), token="K",
                 errors: dict | None = None, save: bytes | None = None):
        self.url, self.board, self.pads, self.footprints = url, Path(board), list(pads), list(footprints)
        self.version, self.token, self.save = version, token, save
        self.errors = {kind: list(names) for kind, names in (errors or {}).items()}
        self.seen, self.tokens = [], []
        self.socket = pynng.Rep0(listen=url)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self) -> None:
        while True:
            try:
                request = ApiRequest.FromString(self.socket.recv())
                self.socket.send(self.answer(request).SerializeToString())
            except pynng.exceptions.NNGException:  # closed (close())
                return

    def answer(self, request: ApiRequest) -> ApiResponse:
        kind = request.message.TypeName().rsplit(".", 1)[-1]
        self.seen.append(kind)
        self.tokens.append(request.header.kicad_token)
        first = self.errors[kind].pop(0) if self.errors.get(kind) else "AS_OK"
        reply = ApiResponse()
        reply.header.kicad_token = self.token
        if request.header.kicad_token not in ("", self.token):
            reply.status.status = ApiStatusCode.AS_TOKEN_MISMATCH
        elif first not in ("AS_OK", "SLOW"):
            reply.status.status = ApiStatusCode.Value(first)
        else:
            if first == "SLOW":
                time.sleep(SLOW_S)
            reply.status.status = ApiStatusCode.AS_OK
            reply.message.Pack(self.response(kind))
        return reply

    def response(self, kind: str):
        if kind == "GetVersion":
            major, minor, patch = self.version
            return base_commands_pb2.GetVersionResponse(version=base_types_pb2.KiCadVersion(
                major=major, minor=minor, patch=patch, full_version=f"{major}.{minor}.{patch}"))
        if kind == "GetOpenDocuments":
            doc = base_types_pb2.DocumentSpecifier(type=base_types_pb2.DOCTYPE_PCB, board_filename=self.board.name)
            doc.project.name, doc.project.path = self.board.stem, str(self.board.parent)
            return editor_commands_pb2.GetOpenDocumentsResponse(documents=[doc])
        if kind == "GetSelection":
            items = []
            for kiid in self.pads:
                pad = board_types_pb2.Pad()
                pad.id.value = kiid
                items.append(pack_any(pad))
            for ref in self.footprints:
                footprint = board_types_pb2.FootprintInstance()
                footprint.reference_field.text.text.text = ref
                items.append(pack_any(footprint))
            return editor_commands_pb2.SelectionResponse(items=items)
        if kind == "SaveDocument" and self.save is not None:
            self.board.write_bytes(self.save)
        return Empty()  # Ping, RefillZones and SaveDocument

    def close(self) -> None:
        self.socket.close()
        self.thread.join(timeout=5)
