#!/usr/bin/env python3
"""housesnap.py -- whole-yard pixels from ONE saved FSEQ frame; no render, video or sequence edits.

    uv run --no-project --with pillow --with lxml --with zstandard --with numpy --python 3.12 python housesnap.py \
        <song>.fseq --at 0:16 [--show <show folder>] [--out yard.png] [--labels] [--gain 1]
    Contact sheet of nearby frames (at most 40):  housesnap.py <song>.fseq 0:16 0:18 --step .5 [--cols 4]
    Active sequence (xLights running, API on):    housesnap.py --active --at 0:16 --out yard.png

Reads: the saved `.fseq` (an FSEQ is sparse; its ranges are laid back out at absolute channels, byte =
channel - 1), the show's `xlights_rgbeffects.xml` (every model's geometry, projected to world XY from its
own definition: custom grid, wiring direction, scale, rotation, world position) and `xlights_networks.xml`
(controller bases, never a hardcoded table). The show folder is `--show`, else the first folder above the
`.fseq` that holds `xlights_rgbeffects.xml`. `--active` asks the running xLights which sequence is open,
checks its show folder matches, and reads that sequence's SAVED `.fseq`; it never reads the live timeline.

Writes: one PNG, a 2D reconstruction (not a House Preview screenshot: no background photo, perspective,
glow, gamma or dimming) with every model the song stores channels for drawn at its layout position, unlit
nodes black, the brighter sample painted last where two LEDs share a screen pixel; and a JSON report beside
it: requested and actual m:ss.mmm, frame index, per-model node and lit counts, geometry notes, the models
the song stores NO channels for. Default output: `<song folder>/analysis/yard-snapshots/yard-<m-ss.mmm>.png`.

Prints: one summary line (time, models, nodes, output path, elapsed), a reminder that only the saved
render was read, and any `POSSIBLY STALE` (a dependency newer than the render) or `NOT IN THIS SEQUENCE`
note. Unsupported geometry, colour order or channel reference, a model only PARTLY stored, or a render
that changes while being read fails loudly rather than drawing something plausible and wrong.
See ../reference/reading-renders.md for accuracy limits.
"""
from pathlib import Path
import argparse, json, math, sys, time
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lxml import etree as E
try:
    from PIL import Image, ImageDraw
except ImportError:                       # importable without Pillow (houseread / litaudit reuse the geometry)
    Image = ImageDraw = None
NO_PIL = ("Pillow is not importable here. Either pip install pillow, or run:\n  uv run --no-project --with pillow "
          "--with lxml --with zstandard --with numpy --python 3.12 python housesnap.py ...")
from fseq import FSEQ
from snap import custom_positions, strand_positions, fallback_positions, node_count, font
from layout import show_folder_of, bases_from_network


def stamp(ms):
    return f'{ms//60000}:{ms%60000/1000:06.3f}'


def milliseconds(s):
    parts=s.split(':')
    if len(parts)>2: raise ValueError('Use m:ss.mmm')
    value=Decimal(parts[-1])+(Decimal(parts[0])*60 if len(parts)==2 else 0)
    if not value.is_finite() or value<0: raise ValueError('Time must be finite and nonnegative')
    return int(value*1000)


def num(m,k,d=0): return float(m.get(k,str(d)))


def geometry(m):
    """World XY projection. Coordinates are node-addressed, never a prop average."""
    kind=m.get('DisplayAs'); wx=num(m,'WorldPosX'); wy=num(m,'WorldPosY')
    note=None; local={}
    if any(abs(num(m,k))>0.0001 for k in ('RotateX','RotateY')):
        raise ValueError(f'{m.get("name")}: tilted 3D model unsupported; refusing a misleading projection')
    if kind=='Single Line':
        n=node_count(m)
        for i in range(n):
            f=i/max(1,n-1)
            if m.get('Dir')=='R': f=1-f
            local[i+1]=(wx+num(m,'X2')*f,wy+num(m,'Y2')*f)
        return local,'Line endpoints exact; LED spacing interpolated'
    if kind=='Poly Line':
        if m.get('cPointData'): raise ValueError('Curved Poly Line unsupported')
        a=list(map(float,m.get('PointData').split(',')));points=list(zip(a[::3],a[1::3]));pts=[]
        for i,(p,q) in enumerate(zip(points,points[1:]),1):
            n=int(m.get(f'Seg{i}','0'))
            for j in range(n):
                f=(j+.5)/n;pts.append((wx+(p[0]+(q[0]-p[0])*f)*num(m,'ScaleX',1),wy+(p[1]+(q[1]-p[1])*f)*num(m,'ScaleY',1)))
        if m.get('Dir')=='R':pts.reverse()
        return dict(enumerate(pts,1)),'Polyline segment spacing approximated; corners from layout'
    if kind=='Arches':
        if int(m.get('NumArches','1'))!=1: raise ValueError('Multi-arch geometry unsupported')
        n=node_count(m); dx=num(m,'X2');dy=num(m,'Y2');length=math.hypot(dx,dy)
        for i in range(n):
            f=i/max(1,n-1)
            if m.get('Dir')=='R':f=1-f
            angle=math.pi*(1-f);x=(1+math.cos(angle))/2;y=math.sin(angle)*num(m,'Height',1)/2
            local[i+1]=(wx+dx*x-dy*y,wy+dy*x+dx*y)
        return local,'Arch height/endpoints from layout; arc, shear and pixel spacing approximated'
    if kind=='Custom':
        pos=custom_positions(m);width=num(m,'CustomWidth');height=num(m,'CustomHeight')
        if num(m,'Depth',1)!=1:raise ValueError('3D custom model unsupported')
        local={n:(x-width/2,height/2-y) for n,(x,y) in pos.items()}
    elif kind in ('Tree','Matrix','Vert Matrix'):
        if m.get('AlternateNodes','false').lower()=='true':raise ValueError('AlternateNodes unsupported')
        pos,_=strand_positions(m,False)
        width=int(m.get('NumStrings'))*int(m.get('StrandsPerString','1'));height=int(m.get('NodesPerString'))//int(m.get('StrandsPerString','1'))
        if kind=='Tree':
            if num(m,'TreeSpiralRotations') or num(m,'TreeType'):raise ValueError('Spiral/flat tree unsupported')
            degrees=num(m,'TreeDegrees',180);rh=height*3;radius=rh/3.6;ratio=num(m,'TreeBottomTopRatio',6)
            for n,(col,row) in pos.items():
                h=1-row/max(1,height-1);theta=math.radians(-degrees/2+num(m,'TreeRotation')+degrees*col/max(1,width-(1 if degrees<350 else 0)))
                rad=radius*(1-h+h/abs(ratio));local[n]=(rad*math.sin(theta),rh*h-rh/2)
            note='Tree uses xLights cone dimensions and strand angles; front XY projection omits perspective/depth occlusion'
        else:
            if m.get('Vertical','true').lower()!='true':width,height=height,width
            local={n:(x-width/2,height/2-y) for n,(x,y) in pos.items()}
    elif kind=='Circle':
        sizes=[int(x) for x in m.get('LayerSizes','').split(',') if x] or [node_count(m)];radius=max(sizes)/2;node=1
        for layer,cnt in enumerate(sizes):
            fraction=layer/max(1,len(sizes)-1)
            if m.get('InsideOut')=='1':fraction=1-fraction
            rad=radius*(1-fraction*(1-num(m,'centerPercent',50)/100)) if len(sizes)>1 else radius
            for i in range(cnt):
                a=(-math.pi if m.get('StartSide')=='B' else 0)+2*math.pi*i/cnt
                if m.get('Dir')=='R':a=-a
                local[node]=(rad*math.sin(a),rad*math.cos(a));node+=1
    elif kind=='Window Frame':
        pos,note=fallback_positions(m);width=max(x for x,y in pos.values());height=max(y for x,y in pos.values())
        local={n:(x-width/2,height/2-y) for n,(x,y) in pos.items()}
    else:raise ValueError(f'Unsupported DisplayAs {kind!r}; no silent omissions')
    theta=math.radians(num(m,'RotateZ'));cs=math.cos(theta);sn=math.sin(theta)
    result={}
    for n,(x,y) in local.items():
        x*=num(m,'ScaleX',1);y*=num(m,'ScaleY',1);result[n]=(wx+x*cs-y*sn,wy+x*sn+y*cs)
    return result,note


def start_channel(m,bases):
    """Absolute 1-based start channel of a <model>: `!Controller:offset` is base + offset - 1; a bare
    number is an xLights-assigned No Controller channel and is taken as is."""
    sc=m.get('StartChannel','')
    if sc.isdigit():return int(sc)
    if sc.startswith('!'):
        ctl,offset=sc[1:].rsplit(':',1)
        return bases[ctl]+int(offset)-1
    raise ValueError(f'Unsupported channel reference {sc!r}')


def sparse_ranges(fs):
    """(0-based absolute start, count) per stored range. xLights writes only the channels of models
    used in the sequence, so a model in the layout but not the song has NO bytes here."""
    return fs.ranges


def read_frame(fs,index,ranges):
    """The frame laid out at ABSOLUTE channel positions (byte = channel-1); fseq.FSEQ does the layout."""
    if not 0<=index<fs.frames:raise ValueError('Requested time outside the rendered sequence')
    if fs.major!=2:raise ValueError('Requires FSEQ v2')
    frame=fs.frame(index)
    if len(frame)!=fs.span:raise ValueError('Incomplete FSEQ frame; wait for Save to finish')
    return frame


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('fseq',nargs='?');ap.add_argument('start',nargs='?');ap.add_argument('end',nargs='?')
    ap.add_argument('--active',action='store_true',help='Read active sequence identity only; never render/save')
    ap.add_argument('--at');ap.add_argument('--show');ap.add_argument('--out');ap.add_argument('--width',type=int,default=1800)
    ap.add_argument('--step',type=float,default=.5);ap.add_argument('--cols',type=int,default=4)
    ap.add_argument('--gain',type=float,default=1);ap.add_argument('--labels',action='store_true')
    a=ap.parse_args();t0=time.monotonic()
    if Image is None:raise SystemExit(NO_PIL)
    if a.active==bool(a.fseq):ap.error('Choose --active OR a saved .fseq')
    if not(a.at or a.start):ap.error('Use --at m:ss.mmm')
    if a.width<320 or a.width>8000 or a.cols<1 or not math.isfinite(a.gain) or a.gain<=0:ap.error('Invalid width, columns or gain')
    if a.active:
        import xl
        xl._guard_not_rendering('yard snapshot');status=xl.call({'cmd':'getOpenSequence'},timeout=10)
        if not status.get('fullseq'):ap.error('No active sequence')
        seq=Path(status['fullseq']);xl.assert_layout(seq,'yard snapshot');path=seq.with_suffix('.fseq');show=show_folder_of(path)
        if a.show and Path(a.show).expanduser().resolve()!=show.resolve():ap.error('--show disagrees with the active layout')
    else:
        path=Path(a.fseq).expanduser().resolve();seq=path.with_suffix('.xsq');show=Path(a.show).expanduser().resolve() if a.show else show_folder_of(path)
    stat=path.stat();fs=FSEQ(path);notes=['Saved FSEQ only: unsaved/unrendered timeline edits cannot be detected.','2D reconstruction, not a native House Preview screenshot; no background photo, gamma/dimming simulation or perspective camera.']
    for dep in [seq,show/'xlights_rgbeffects.xml',show/'xlights_networks.xml']:
        if dep.exists() and dep.stat().st_mtime>stat.st_mtime+2:notes.append(f'POSSIBLY STALE: {dep.name} is newer than the render')
    roots=E.parse(str(show/'xlights_rgbeffects.xml')).getroot().find('models');bases=bases_from_network(show);starts={m.get('name'):start_channel(m,bases) for m in roots};models=[]
    ranges=sparse_ranges(fs);span=max(s+n for s,n in ranges);absent=[]
    for m in roots:
        name=m.get('name');pos,note=geometry(m)
        if not pos or min(pos)<1:raise ValueError(f'{name}: invalid node geometry')
        if m.get('StringType') not in ('RGB Nodes','RGBW Nodes'):raise ValueError(f'{name}: unsupported color order/type')
        stride=4 if m.get('StringType')=='RGBW Nodes' else 3;base=starts[name];end=base+max(pos)*stride-1
        stored=[s<=base-1 and end<=s+n for s,n in ranges]
        if not any(stored):
            if any(base-1<s+n and end>s for s,n in ranges):raise ValueError(f'{name}: only partly stored in the FSEQ; refusing incorrect colors')
            absent.append(name);continue   # in the layout, not in this song: xLights stored no channels for it
        nextbase=min([s for s in starts.values() if s>base]+[span+1])
        if base<1 or end>=nextbase:raise ValueError(f'{name}: node channels overlap next model or exceed FSEQ')
        models.append((m,pos,base,stride))
        if note:notes.append(f'{name}: {note}')
    if absent:notes.append('NOT IN THIS SEQUENCE (no channels stored, not drawn): '+', '.join(absent))
    allxy=[xy for m,pos,b,s in models for xy in pos.values()];xs,ys=zip(*allxy);x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys);scale=(a.width-40)/(x1-x0);height=math.ceil((y1-y0)*scale)+70
    lo=milliseconds(a.at or a.start);hi=milliseconds(a.end) if a.end else lo
    if hi<lo or a.step<=0 or not math.isfinite(a.step):ap.error('Invalid contact-sheet range/step')
    step=max(1,round(a.step*1000))
    if (hi-lo)//step+1>40:ap.error('At most 40 frames; increase --step')
    times=list(range(lo,hi+1,step))
    tiles=[];summaries=[]
    for ms in times:
        idx=ms//fs.step;frame=read_frame(fs,idx,ranges);img=Image.new('RGB',(a.width,height));draw=ImageDraw.Draw(img);counts={};dots=[]
        for m,pos,base,stride in models:
            count=0
            for n,(x,y) in pos.items():
                off=base-1+(n-1)*stride;rgb=list(frame[off:off+3])
                if stride==4:rgb=[min(255,v+frame[off+3]) for v in rgb]
                if max(rgb)>0:count+=1
                col=tuple(min(255,round(v*a.gain)) for v in rgb)
                if max(col):dots.append((max(col),20+(x-x0)*scale,45+(y1-y)*scale,col,m.get('DisplayAs')=='Matrix'))
            counts[m.get('name')]={'nodes':len(pos),'lit':count}
            if a.labels:draw.text((20+(sum(x for x,y in pos.values())/len(pos)-x0)*scale,45+(y1-max(y for x,y in pos.values()))*scale),m.get('name'),fill=(140,140,140),font=font(10))
        # Bright samples paint last where multiple physical LEDs share a screen pixel.
        for _,x,y,col,matrix in sorted(dots):
            r=.5 if matrix else .8;draw.ellipse((x-r,y-r,x+r,y+r),fill=col)
        draw.text((12,8),f'{path.stem} | {stamp(idx*fs.step)} | {len(models)} models | saved render / 2D reconstruction',fill=(210,210,210),font=font(16))
        tiles.append(img);summaries.append({'requested':stamp(ms),'actual':stamp(idx*fs.step),'frame':idx,'models':counts})
    cols=min(a.cols,len(tiles));rows=math.ceil(len(tiles)/cols);sheet=Image.new('RGB',(a.width*cols,height*rows))
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%cols)*a.width,(i//cols)*height))
    if (path.stat().st_size,path.stat().st_mtime_ns)!=(stat.st_size,stat.st_mtime_ns):raise ValueError('Render changed while reading; retry after Save settles')
    out=Path(a.out).expanduser().resolve() if a.out else path.parent/'analysis'/'yard-snapshots'/f'yard-{stamp(lo).replace(":","-")}.png'
    out.parent.mkdir(parents=True,exist_ok=True);sheet.save(out)
    report={'fseq':str(path),'show':str(show),'fseq_mtime':stat.st_mtime,'gain':a.gain,'notes':notes,'frames':summaries,'elapsed_seconds':round(time.monotonic()-t0,3)}
    out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');fs.f.close()
    print(f'{stamp(lo)}: {len(models)} models, {sum(len(p) for m,p,b,s in models)} nodes -> {out} ({report["elapsed_seconds"]}s)')
    print('Saved render only; no xLights render, save, playback or video export performed. Geometry limitations are recorded in '+str(out.with_suffix('.json')))
    for note in notes:
        if note.startswith(('POSSIBLY','NOT IN THIS')):print(note)

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError) as e:raise SystemExit(str(e))
