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
from kipy.proto.common.types import KiCadObjectType, base_types_pb2
from kipy.util import pack_any

SLOW_S = 1.5  # how late a "SLOW" answer comes: past the helper's 1 s (button.TIMEOUT_MS)


class FakeKiCad:
    """KiCad's API server at `url` (ipc://...), as kipy 0.8 meets KiCad 9.0.7's. Its token is `token`: a request with
    another, non-empty one gets AS_TOKEN_MISMATCH. Its PCB editor has the board file `board` open (GetOpenDocuments:
    its folder and file name) with the pads `pads` (KIIDs), the footprints `footprints` (references) and the tracks
    `tracks`, arcs `arcs` and vias `vias` (KIIDs) selected (GetSelection, which answers only the types the request
    asks for); GetVersion answers `version`; RefillZones and Ping answer Empty; SaveDocument writes `save` into
    `board` when given, as KiCad's save writes the edits it holds, and answers Empty. `errors` maps a request's type
    name to what it answers first, one per request: an AS_ status name, or "SLOW", its usual answer SLOW_S late, as
    KiCad answers once its main thread is free of a zone fill or a large save. `seen` lists the requests' type names
    in order, and `tokens` the tokens they carried."""

    def __init__(self, url: str, board: Path, *, pads=(), footprints=(), tracks=(), arcs=(), vias=(),
                 version=(9, 0, 7), token="K", errors: dict | None = None, save: bytes | None = None):
        self.url, self.board, self.pads, self.footprints = url, Path(board), list(pads), list(footprints)
        self.tracks, self.arcs, self.vias = list(tracks), list(arcs), list(vias)
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
            reply.message.Pack(self.response(kind, request))
        return reply

    def response(self, kind: str, request: ApiRequest):
        if kind == "GetVersion":
            major, minor, patch = self.version
            return base_commands_pb2.GetVersionResponse(version=base_types_pb2.KiCadVersion(
                major=major, minor=minor, patch=patch, full_version=f"{major}.{minor}.{patch}"))
        if kind == "GetOpenDocuments":
            doc = base_types_pb2.DocumentSpecifier(type=base_types_pb2.DOCTYPE_PCB, board_filename=self.board.name)
            doc.project.name, doc.project.path = self.board.stem, str(self.board.parent)
            return editor_commands_pb2.GetOpenDocumentsResponse(documents=[doc])
        if kind == "GetSelection":
            asked = editor_commands_pb2.GetSelection()
            request.message.Unpack(asked)
            items = []
            for kot, message, names in ((KiCadObjectType.KOT_PCB_PAD, board_types_pb2.Pad, self.pads),
                                        (KiCadObjectType.KOT_PCB_FOOTPRINT, board_types_pb2.FootprintInstance,
                                         self.footprints),
                                        (KiCadObjectType.KOT_PCB_TRACE, board_types_pb2.Track, self.tracks),
                                        (KiCadObjectType.KOT_PCB_ARC, board_types_pb2.Arc, self.arcs),
                                        (KiCadObjectType.KOT_PCB_VIA, board_types_pb2.Via, self.vias)):
                if kot not in asked.types:
                    continue
                for name in names:
                    item = message()
                    if kot == KiCadObjectType.KOT_PCB_FOOTPRINT:
                        item.reference_field.text.text.text = name  # a footprint by its reference
                    else:
                        item.id.value = name  # the rest by KIID
                    items.append(pack_any(item))
            return editor_commands_pb2.SelectionResponse(items=items)
        if kind == "SaveDocument" and self.save is not None:
            self.board.write_bytes(self.save)
        return Empty()  # Ping, RefillZones and SaveDocument

    def close(self) -> None:
        self.socket.close()
        self.thread.join(timeout=5)
