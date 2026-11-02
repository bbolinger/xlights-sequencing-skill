"""Minimal FSEQ v2 reader. Gotcha (CLAUDE.md): the compression block count is
(byte20>>4)<<8 | byte21, not byte21 -- getting it wrong silently decodes ~2% of frames."""
import struct, zstandard, zlib

class FSEQ:
    def __init__(self, path):
        f = open(path, "rb"); self.f = f
        h = f.read(32)
        assert h[:4] == b"PSEQ", h[:4]
        self.data_off = struct.unpack("<H", h[4:6])[0]
        self.minor, self.major = h[6], h[7]
        self.var_off = struct.unpack("<H", h[8:10])[0]
        self.channels = struct.unpack("<I", h[10:14])[0]
        self.frames = struct.unpack("<I", h[14:18])[0]
        self.step = h[18]
        self.comp = h[20] & 0x0F
        self.blocks = ((h[20] >> 4) << 8) | h[21]
        self.sparse = h[22]
        assert 32 + self.blocks * 8 + self.sparse * 6 == self.var_off, \
            f"sanity: 32+{self.blocks}*8+{self.sparse}*6 != {self.var_off}"
        tbl = f.read(self.blocks * 8)
        idx = [struct.unpack("<II", tbl[i*8:i*8+8]) for i in range(self.blocks)]
        # the table is padded with unused (0,0) slots; a reverse search matches those
        # first and silently returns an empty frame
        self.index = [e for e in idx if e[1] > 0]
        # Sparse ranges (0-based absolute start, count). xLights stores only the channels of
        # models used in the sequence (09-30: the pumpkins/floods/wreaths made this non-trivial),
        # so frame() lays them back out at absolute positions: byte = absolute channel - 1.
        sp = f.read(self.sparse * 6)
        self.ranges = [(int.from_bytes(sp[i*6:i*6+3], "little"), int.from_bytes(sp[i*6+3:i*6+6], "little"))
                       for i in range(self.sparse)] or [(0, self.channels)]
        assert sum(n for _, n in self.ranges) == self.channels, "sparse ranges != channel count"
        self.span = max(s + n for s, n in self.ranges)
        self._cache = {}

    def _block(self, bi):
        if bi in self._cache: return self._cache[bi]
        off = self.data_off + sum(l for _, l in self.index[:bi])
        self.f.seek(off)
        raw = self.f.read(self.index[bi][1])
        if self.comp == 1:
            d = zstandard.ZstdDecompressor().decompressobj().decompress(raw)
        elif self.comp == 2:
            d = zlib.decompress(raw)
        else:
            d = raw
        self._cache = {bi: d}
        return d

    def _absolute(self, raw):
        if self.ranges == [(0, self.channels)]:
            return raw
        out = bytearray(self.span); o = 0      # channels not stored read as 0 (dark)
        for s, c in self.ranges:
            out[s:s + c] = raw[o:o + c]; o += c
        return bytes(out)

    def frame(self, n):
        if self.comp == 0 and not self.index:          # uncompressed v2: no block table
            self.f.seek(self.data_off + n * self.channels)
            return self._absolute(self.f.read(self.channels))
        for bi in range(len(self.index) - 1, -1, -1):
            if self.index[bi][0] <= n:
                d = self._block(bi)
                off = (n - self.index[bi][0]) * self.channels
                return self._absolute(d[off:off + self.channels])
        raise IndexError(n)


def rgb(frame, abs_start_channel, node):
    """RGB of one node in a decoded frame.

    `abs_start_channel` is the model's absolute start channel, 1-based: controller base +
    (StartChannel offset) - 1, e.g. `!CONTROLLER:541` -> 3397 + 541 - 1 = 3937.  The frame is
    a 0-based byte array, so that number is one MORE than the byte index.  Using it directly
    reads (G, B, R-of-the-next-node): on 2026-09-04 that made pure red look like pure blue
    and a green tombstone bed look red, and every colour reported from a render before that
    was shifted.  Always read through this helper.
    """
    o = (abs_start_channel - 1) + (node - 1) * 3
    return tuple(frame[o:o + 3])
