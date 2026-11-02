# The `.xsq`, the `.fseq` and the layout file

What an agent must know about xLights' files before writing or reading one. Each item cost a
wrong conclusion on one show; the dates say when it was learned.

## 1. Skeleton

One XML document, in this order (names below are made up; the shape is real):

```xml
<xsequence BaseChannel="0" ChanCtrlBasic="0" ChanCtrlColor="0" FixedPointTiming="1" ModelBlending="true">
  <head>
    <sequenceTiming>25 ms</sequenceTiming>
    <mediaFile>/absolute/path/to/song.mp3</mediaFile>
    <sequenceDuration>129.050</sequenceDuration>      <!-- numeric seconds; xLights parses it -->
  </head>
  <ColorPalettes>
    <ColorPalette>C_BUTTON_Palette1=#B0C41A,C_BUTTON_Palette2=#7C143C,…,C_CHECKBOX_Palette1=1,C_CHECKBOX_Palette2=1</ColorPalette>
  </ColorPalettes>
  <EffectDB>
    <Effect>E_CHECKBOX_ColorWash_HFade=1,E_TEXTCTRL_ColorWash_Cycles=0.8,T_TEXTCTRL_Fadein=1.20,T_TEXTCTRL_Fadeout=1.60</Effect>
  </EffectDB>
  <DisplayElements>                                     <!-- the sequencer's VIEW LIST -->
    <Element collapsed="false" type="model" name="Roofline" visible="true" />
    <Element collapsed="false" type="timing" name="Lyrics" visible="true" views="" active="false" />
  </DisplayElements>
  <ElementEffects>                                      <!-- what RENDERS -->
    <Element type="model" name="Roofline">
      <EffectLayer>
        <Effect ref="0" name="Color Wash" startTime="61950" endTime="68600" palette="0" />
      </EffectLayer>
      <EffectLayer />                                   <!-- an empty layer is xLights' own -->
      <SubModelEffectLayer name="Outer Ring">
        <Effect ref="5" name="On" startTime="38025" endTime="41275" palette="4" />
      </SubModelEffectLayer>
    </Element>
    <Element type="timing" name="Lyrics">
      <EffectLayer><Effect label="…" startTime="0" endTime="11050" /></EffectLayer>
    </Element>
  </ElementEffects>
  <lastView>0</lastView> <SequenceMedia /> <DataLayers>…</DataLayers> <TimingTags>…</TimingTags>
</xsequence>
```

- A model-row `<Effect>` carries `ref` (0-based index into `<EffectDB>`), `name` (the type as the
  app spells it: `Color Wash`, `SingleStrand`, `VU Meter`), `startTime`/`endTime` (integer ms) and
  `palette` (0-based index into `<ColorPalettes>`); many effects share one `ref`: the DB is
  deduplicated. An `id` appears on some effects; leave it as found. A timing mark carries only
  `label`, `startTime`, `endTime`.
- A submodel's effects are NESTED: `<SubModelEffectLayer name="Outer Ring">` inside the model's
  `<Element>`, never a separate `Model/Submodel` element; its `layer` attribute appears only from
  the second submodel layer on.

## 2. Two lists of elements: scope every reader and writer to `<ElementEffects>`

`<Element type="model" name="X">` occurs twice per row: in `<DisplayElements>` (the view list) and
in `<ElementEffects>` (what renders). The view list comes first, so `root.iter("Element")` finds
it first. On 2026-09-04 two tools looked elements up that way and appended 199 effects into the
view list. xLights rendered nothing from them, and every
check made with the same iterator ("0 lost / 199 added", validator PASSED) counted the junk and
reported success. The owner, three times: *"no eyes still."*

The mirror (2026-09-22): a NEW row written into `<ElementEffects>` only validated, rendered, saved,
and came back with no row at all: xLights silently drops an `ElementEffects` row the view list
does not know. **A new row goes in BOTH lists**, same `name`, in the two forms §1 shows.

So: `root.find("ElementEffects")` everywhere; a count made any other way is not evidence. The
fastest proof is grep/awk on the raw XML of the element the effect should be in (§9).

## 3. Layers and rows

**Inside one element, layer 0 is ON TOP.** `PixelBuffer.cpp` mixes layers from `numLayers−1` down
to 0, so the first `<EffectLayer>` paints last (`Normal`, the default `T_CHOICE_LayerMethod`, is
alpha-over). On 2026-09-11 a picture put on the LAST layer showed 79 white nodes where it had
~900, under six layers of bed; on layer 0, 886.

**Between elements, a later ROW paints over an earlier one, only where it DRAWS.** With
`ModelBlending="true"` each row alpha-blends over what the rows above wrote (`RenderEngine.cpp`
OutputFrame + `PixelBuffer.cpp` Mix_Normal): a full-cover effect (Color Wash, Fire, Video) buries
what is above it; Bars or a chase cover only their lit pixels. A prop's own effects show over a
group bed only if the prop's row sits BELOW the group's. Row order is the order of `<Element>`s in
the file and is load-bearing: a writer that re-sorted alphabetically destroyed hand-arranged
rows. Never sort; a fix is a narrower group appended as a NEW row at the end, never a move.

## 4. Time

- Integer ms on a 25 ms frame (`<sequenceTiming>25 ms</sequenceTiming>`); a sub-frame effect
  renders nothing. Write on the grid: a Save snaps off-grid values (27589 → 27600; 5680 → 5675),
  and a tool that re-derives them from seconds puts them back, so effects toggle by a frame on
  every run/save cycle and a diff against the approved snapshot never passes.
- **A Save rewrites the whole file**: times snap, settings and palette strings normalise, keys at
  their defaults are dropped (`B_CHOICE_PerPreviewCamera=2D` vanished), `<EffectDB>` and
  `<ColorPalettes>` re-index. An exact-string diff across one save reported 458 lost / 461 added
  when the truth was 0 / 6. After any save, re-baseline and compare by **(element, effect name,
  start ± 1 frame, end ± 1 frame)**, never by raw string or bytes.

## 5. Settings strings and palettes

An `<EffectDB>` entry is `key=value,key=value,…`. Prefix = owning panel: `E_` effect; `B_` buffer
(`B_CHOICE_BufferStyle`, `B_CHOICE_BufferTransform`, `B_CHOICE_PerPreviewCamera`, `B_SLIDER_Blur`);
`T_` timing/layer (`T_TEXTCTRL_Fadein`/`Fadeout`, `T_CHOICE_LayerMethod`, `T_CHECKBOX_Canvas`);
`C_` colour, only in `<ColorPalettes>` (`C_BUTTON_Palette1..8=#RRGGBB`; `C_CHECKBOX_PaletteN=1`
marks a slot active). Infix = widget (`SLIDER`, `CHOICE`, …); tail = effect
and control (`E_SLIDER_Bars_BarCount`, `E_CHOICE_Chase_Type1`).

- **An unknown key is silently ignored** and the effect falls back to its default: renders fine,
  looks wrong. Copy KEYS from the show's own files (counted by use, per target type, excluding
  your own output); never bake one sample's VALUE in as a constant. Absence from the show's files does
  not prove a key invalid: Save omits defaults. A Shader's keys are its own ISF inputs (`R/G/B`
  in one, lowercase `r/g/b` in another).
- **A model's default buffer is its WIRING, not its shape.** A Single Line or one-arch Arches is
  1 × N: ONE PIXEL TALL, so any directional effect (`Fire` `Location=Bottom`, Bars up, a wipe) is
  the whole strand at once, a solid fill. Compute the buffer rows first (§8); one row means
  `B_CHOICE_BufferStyle=Per Model Per Preview` + `B_CHOICE_PerPreviewCamera=2D` (the buffer becomes
  the prop's footprint). An irregular multiprop wants `Per Model Default Deep`.

## 6. Timing tracks

`<Element type="timing" name="…">` in `<ElementEffects>`, one or more `<EffectLayer>`s of
`<Effect label="…" startTime endTime />`; its `<DisplayElements>` row adds `views=""
active="false"`. The show's lyric tracks carry three layers: phrase, word, mouth shape (viseme).
**Faces reads the mouth from the THIRD layer**: phonemes left on layer 2 rendered the closed
rest mouth on every frame. Faces binds by name: `E_CHOICE_Faces_TimingTrack=<track>`, `E_CHOICE_Faces_FaceDefinition=<faceInfo
name>`, `E_CHOICE_Faces_Eyes=Open|Closed|Auto`, `E_CHECKBOX_Faces_Outline`. Aligner word bounds
overlap by a few ms: clamp at write time (later mark to the previous end; drop sub-frame marks). A check that iterates all elements without filtering on `type` reports those as effect
overlaps.

## 7. The `.fseq` (render output)

A render writes no `.fseq`; a **Save** does, and the save API returns while the file is still
being written: read it before the size has held ~2 s and every frame past 1:00 is black
(2026-09-13). Decoding it costs no GPU and beats a screenshot.

**FSEQ v2 header (32 bytes):** `PSEQ`; 4-5 data offset (u16); 6 minor, 7 major; 8-9 variable-data
offset; 10-13 channels (u32); 14-17 frames (u32); 18 step ms; byte 20 low nibble = compression
(0 none, 1 zstd, 2 zlib); **block count = `(byte20 >> 4) << 8 | byte21`**, not `byte21` (wrong,
it silently decodes ~2 % of frames); 22 sparse-range count. Then the block table (first frame,
byte length; 8 bytes each), **padded with `(0, 0)` slots**: drop zero-length entries or a reverse
search for frame N hits padding and returns an empty frame. Then the sparse ranges (3-byte
0-based start, 3-byte count). Sanity: `32 + blocks*8 + sparse*6 == variable-data offset`. Frame N
is in the last block whose first frame ≤ N, at `(N − first) × channels` into the decompressed
block.

- **SPARSE: xLights stores only the channels of models in that song.** Indexing the packed bytes
  as absolute breaks the day the layout gains a model the song does not use (one file: ranges
  1-23,379 and 25,009-124,869). Lay each range out at its absolute position; a model not in the
  song reads dark; say so by name, not 0 %.
- **Byte index = absolute channel − 1.** Absolute = controller base (networks file, definition
  order) + `StartChannel` offset − 1; the frame is 0-based, so one more −1. Read through a helper
  that takes a **1-based node**: `offset = (abs_start − 1) + (node − 1) × stride`. Reading at the
  channel number gives (G, B, R-of-next-node): pure red read as blue (2026-09-04); passing
  `node − 1` to a helper that already subtracts shifts every reading by a node and still looks
  plausible (2026-09-06).
- **Stride 3 for `RGB Nodes`, 4 for `RGBW Nodes`**: a 3-stride read is on the wrong pixel from
  node 2 on; carry base and stride per model. **No bounds checking**: past a model's node count
  you read its neighbour and it looks right; bound by the NEXT model's start channel.
- **No Controller models are numbered by xLights itself**: by NAME, after the last controller
  (`ModelManager.cpp`); the stored `StartChannel` is ignored.
- **A sequence whose LENGTH changed keeps the old `.fseq`'s frame count** through open + render +
  save: a song cut from 5:58 to 4:21 saved 14,319 frames, dark after 4:20.5; 1:37 of dead air on
  the player. Move the old `.fseq` aside before opening; check frames × step against
  `sequenceDuration` (5,162 × 25 ms = 129.05 s = `129.050`).
- Sample **strictly inside** a span (a boundary frame holds the neighbour) and take the peak: a
  900 ms effect peaks 200 ms in. **Count lit pixels on EXCLUSIVE node sets; never `max()` over
  overlapping submodels** (two submodels sharing one node both read 255, 2026-09-22). Confirm the
  mapping first on a frame you can predict (a Faces
  effect must light non-ring nodes).

## 8. The layout file (`xlights_rgbeffects.xml`)

Models, submodels, groups and faces live here, per show folder, so **the loaded show folder is
part of a sequence's identity**: a save against another folder's layout can write out every model
that layout lacks (2026-09-19). Check which folder is loaded before every open.

- `<models><model name DisplayAs StartChannel="!Controller:offset" StringType="RGB Nodes|RGBW
  Nodes" Dir StartSide …>` with children `<subModel name line0="1, 4, 7, 10" type="ranges">` (a
  range `13-2` runs backwards), `<faceInfo Eyes-Open="…" Mouth-AI="…" FaceOutline="…">` (node
  lists per part), `<stateInfo>`, `<ControllerConnection>`, `<dimmingCurve>`, `<Aliases>`.
- **Buffer rows come from `DisplayAs` + the model's own attributes**: Arches `NumArches ×
  NodesPerArch` (1 × 70 = one row); Single Line `NumStrings × NodesPerString` (1 × 60 = one row);
  Tree `NumStrings × strands` tall, `NodesPerString / strands` wide (8 × 4 × 400 → 32 × 100);
  Matrix `NumStrings × NodesPerString`; Custom `CustomWidth × CustomHeight`, with
  `CustomModelCompressed="node,row,col;…"` (row 0 = top) placing every node. Other `DisplayAs`:
  compute from the attributes and confirm in the app.
- `<modelGroups><modelGroup name models="A,B,Other Group,Model/Sub" layout="minimalGrid"
  DefaultCamera="2D">`. A group may hold groups and may name a SUBMODEL (`Model/Sub`), reaching a
  prop's submodels without claiming the prop. **Check what a group EXPANDS to, never its name**:
  one named for a third of the yard swallowed three multiprops. Expand recursively to the leaf
  before placing or counting. A `minimalGrid` buffer is its members' bounding grid: an integer
  translation of the whole yard is render-neutral, a scale is not.
- A group or model name that does not resolve is silent dead air. Validate every name.

## 9. Hand-checks on the raw XML

The proof an effect is real is the text of the element it should be in. BSD and GNU awk alike.

```sh
# effects xLights will render, by type (never count the view list);
# the tag is <Effect name=…>, case-sensitive
awk '/<ElementEffects>/{f=1} /<\/ElementEffects>/{f=0} f && /<Effect /' song.xsq \
  | grep -o ' name="[^"]*"' | sort | uniq -c | sort -rn
# every row in BOTH lists: prints nothing when they agree
diff <(awk '/<DisplayElements>/{f=1} /<\/DisplayElements>/{f=0} f && /<Element /' song.xsq | grep -o 'name="[^"]*"' | sort) \
     <(awk '/<ElementEffects>/{f=1}  /<\/ElementEffects>/{f=0}  f && /<Element /' song.xsq | grep -o 'name="[^"]*"' | sort)
# everything on one element, submodel layers included
awk '/<ElementEffects>/{f=1} f && /<Element type="model" name="Roofline">/{g=1} g{print} g && /<\/Element>/{exit}' song.xsq
# off-grid times (must be 0)
awk '/<ElementEffects>/{f=1} /<\/ElementEffects>/{f=0} f && /<Effect /' song.xsq \
  | grep -o 'Time="[0-9]*"' | tr -dc '0-9\n' | awk '$1 % 25 {n++} END {print n+0, "off-grid"}'
# render header: frames x step must equal <sequenceDuration>
python3 -c 'import struct,sys;h=open(sys.argv[1],"rb").read(32);print(struct.unpack("<I",h[14:18])[0],"frames x",h[18],"ms")' song.fseq
```

When the owner says it is not on screen and a count says it is, the count is scoped wrong, reading
the wrong byte, or reading the view list. Start there.
