"""Scenes 03-06 as the page shows them, offline: the film frame, the scene's headline mapped onto its plane in the
world, the film again in front of it wherever the matte says something is nearer, the two notes riding with the cube
(Scene 03) and the finale (Scene 06). Same numbers as src/main.js and src/styles.css, so stills and preview videos match
the page. The track says which scene it is (Scene 04-06's has a 'head' frame).

python3 tools/compose_s3.py <frames dir> <mattes dir (m_####.png|webp)> <track.json> <out dir> <first> [last] [--css W]
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = os.environ.get('SDC_FONT', '/private/tmp/claude-501/-Users-piyushkumar-claude-squaredc-home/6a470a90-9c4d-44e9-a4b4-5534c6b58d09/scratchpad/fonts/Axiforma-Light.ttf')
SAND = (242, 235, 217)
YELLOW = (251, 177, 0)

# styles.css: .moment / .moment-2, and main.js MOMENTS (when each rises in and lets go)
BOX_W, BOX_H, LS, PAD = 2000, 360, -0.045, 0.04
SPECS = {'s03': dict(words=('Ideas attract', 'ideas.'), FS=134, MT=112, GL=814, GR=1605, in1=296, in2=304, out=344, outLen=26),
         's04': dict(words=('And ideas become', 'worlds.'), FS=112, MT=124, GL=969, GR=1620, in1=852, in2=860, out=893, outLen=30)}
FONT_REG = FONT.replace('Light', 'Regular')
LOCKUP = os.path.join(os.path.dirname(FONT), 'lockup.png')
FINALE = ('Different ideas.', 'Different worlds.', 'One universe.')
FINALE_AT = (952, 962, 972, 982, 990)
ASC = 0.771                               # hhea ascent: with line-height 1 the baseline sits 0.771em below the top
# main.js: overlays() / noteAt()
NOTE_TEXT = ('And when they come together,', 'something new begins.')


def smooth(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


def run_width(font, s, ls):
    return sum(font.getlength(c) + ls for c in s)


def draw_run(draw, font, s, x, baseline, ls, fill):
    for c in s:
        draw.text((x, baseline), c, font=font, fill=fill, anchor='ls')
        x += font.getlength(c) + ls


def headline_box(m1, m2, sp, scale=1.0):
    """The .moment box, words risen in by m1 / m2 (translateY inside an overflow:hidden line), at `scale`."""
    FS, MT, GL, GR = sp['FS'], sp['MT'], sp['GL'], sp['GR']
    W, H = int(BOX_W * scale), int(BOX_H * scale)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    f = ImageFont.truetype(FONT, int(round(FS * scale)))
    ls = LS * FS * scale; pad = PAD * FS * scale
    top = MT * scale; line_h = FS * scale; base = top + ASC * FS * scale
    for word, m, right in ((sp['words'][0], m1, GL), (sp['words'][1], m2, None)):
        if m <= 0: continue
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        w = run_width(f, word, ls)
        x = (right * scale - pad - w) if right else (GR * scale + pad)
        dy = (1 - m) * 1.08 * line_h
        draw_run(d, f, word, x, base + dy, ls, (*SAND, int(255 * m)))
        # the line's own mask: nothing shows below the bottom of its box (overflow hidden)
        clip = Image.new('L', (W, H), 0)
        ImageDraw.Draw(clip).rectangle([0, top, W, top + line_h + 0.14 * FS * scale], fill=255)
        layer.putalpha(Image.fromarray((np.asarray(layer.getchannel('A'), np.float32) * np.asarray(clip, np.float32) / 255).astype(np.uint8)))
        img = Image.alpha_composite(img, layer)
    return img


def perspective_coeffs(dst, src):
    """PIL wants output->input: solve the homography taking dst points (on the frame) to src points (in the box)."""
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, float), np.array(b, float)).tolist()


def finale(out, idx, css_w):
    """styles.css .finale: centred at 47vh, three lines rising in, then the sign-off and the button."""
    W, H = out.size; k = W / css_w; vh = H / 100
    v = [smooth((idx - a) / 18) for a in FINALE_AT]
    if v[0] <= 0: return out
    fs = min(68, max(34, 0.037 * css_w)) * k
    f = ImageFont.truetype(FONT, int(round(fs))); ls = -0.035 * fs
    lay = Image.new('RGBA', out.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    top = 47 * vh
    for i, (line, m) in enumerate(zip(FINALE, v[:3])):
        if m <= 0: continue
        w = run_width(f, line, ls); base = top + i * 1.04 * fs + ASC * fs + (1.04 - 1) * fs / 2
        clip_top, clip_bot = top + i * 1.04 * fs, top + (i + 1) * 1.04 * fs + 0.08 * fs
        line_l = Image.new('RGBA', out.size, (0, 0, 0, 0))
        draw_run(ImageDraw.Draw(line_l), f, line, (W - w) / 2, base + (1 - m) * 1.08 * fs, ls, (*SAND, int(255 * m)))
        clip = Image.new('L', out.size, 0); ImageDraw.Draw(clip).rectangle([0, clip_top, W, clip_bot], fill=255)
        line_l.putalpha(Image.fromarray((np.asarray(line_l.getchannel('A'), np.float32) * np.asarray(clip, np.float32) / 255).astype(np.uint8)))
        lay = Image.alpha_composite(lay, line_l)
    y = top + 3 * 1.04 * fs + 34 * k
    if v[3] > 0:                                              # the lockup and the line beside it
        tf = ImageFont.truetype(FONT, int(round(min(19, max(15, 0.0115 * css_w)) * k)))
        tag = 'Your Product Team. Without Hiring One.'
        logo = Image.open(LOCKUP).convert('RGBA'); lh = int(30 * k); logo = logo.resize((int(logo.width * lh / logo.height), lh))
        tw = tf.getlength(tag); total = logo.width + 18 * k + tw; x0 = (W - total) / 2; dy = (1 - v[3]) * 12 * k
        a = np.asarray(logo.getchannel('A'), np.float32) * v[3]; logo.putalpha(Image.fromarray(a.astype(np.uint8)))
        lay.alpha_composite(logo, (int(x0), int(y + dy)))
        ImageDraw.Draw(lay).text((x0 + logo.width + 18 * k, y + dy + lh / 2), tag, font=tf, fill=(*SAND, int(255 * 0.78 * v[3])), anchor='lm')
    if v[4] > 0:                                              # the button
        bf = ImageFont.truetype(FONT_REG, int(round(15 * k))); label = 'Explore Our Work  →'
        bw = bf.getlength(label) + 60 * k; bh = 54 * k; by = y + 30 * k + 30 * k + (1 - v[4]) * 12 * k; bx = (W - bw) / 2
        ImageDraw.Draw(lay).rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh / 2, fill=(*SAND, int(255 * v[4])))
        ImageDraw.Draw(lay).text((W / 2, by + bh / 2), label, font=bf, fill=(7, 2, 14, int(255 * v[4])), anchor='mm')
    return Image.alpha_composite(out, lay)


def compose(film, matte, T, idx, css_w, sp, notes_on):
    W, H = film.size
    k = W / css_w                                             # output px per CSS px
    out = film.convert('RGBA')
    m1, m2 = smooth((idx - sp['in1']) / 18), smooth((idx - sp['in2']) / 18)
    stay = 1 - smooth((idx - sp['out']) / sp['outLen'])
    if T and T.get('q') and m1 > 0 and stay > 0:
        sc = 1.25
        box = headline_box(m1, m2, sp, sc)
        dst = [(x * W, y * H) for x, y in T['q']]
        src = [(0, 0), (BOX_W * sc, 0), (BOX_W * sc, BOX_H * sc), (0, BOX_H * sc)]
        warped = box.transform((W, H), Image.PERSPECTIVE, perspective_coeffs(dst, src), Image.BICUBIC)
        if stay < 1:
            a = np.asarray(warped.getchannel('A'), np.float32) * stay
            warped.putalpha(Image.fromarray(a.astype(np.uint8)))
        under = Image.alpha_composite(out, warped)
        if matte is not None:                                  # the film again, wherever something is in front
            M = np.asarray(matte.resize((W, H), Image.BILINEAR), np.float32)[..., None] / 255.0
            o = np.asarray(film.convert('RGB'), np.float32) * M + np.asarray(under.convert('RGB'), np.float32) * (1 - M)
            out = Image.fromarray(o.clip(0, 255).astype(np.uint8)).convert('RGBA')
        else:
            out = under
    if not notes_on:
        return finale(out, idx, css_w).convert('RGB')
    # notes
    if T:
        d = ImageDraw.Draw(out)
        nf = ImageFont.truetype(FONT, int(round(min(30, max(20, 0.018 * css_w)) * k)))
        cx, cy, rr = T['c'][0] * W, T['c'][1] * H, T['r'] * W
        for text, (a, b) in zip(NOTE_TEXT, BEATS):
            p = smooth((idx - a) / 20) * (1 - smooth((idx - b) / 16))
            if p <= 0.001: continue
            tw = nf.getlength(text); th = (min(30, max(20, 0.018 * css_w)) * 1.2 + 0.14 * min(30, max(20, 0.018 * css_w))) * k
            L = max(26 * k, rr * 0.75)
            dr = 1 if cx + rr * 0.5 + L + tw + 40 * k <= W - 24 * k else -1
            ax, ay = cx + dr * rr * 0.5, cy - rr * 0.5
            ex, ey = ax + dr * L, ay - L
            fx = ex + dr * (tw + 18 * k)
            seg = [((ax, ay), (ex, ey)), ((ex, ey), (fx, ey))]
            total = math.hypot(ex - ax, ey - ay) + abs(fx - ex); drawn = total * smooth(p * 1.25)
            line = Image.new('RGBA', out.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(line)
            for (x0, y0), (x1, y1) in seg:
                sl = math.hypot(x1 - x0, y1 - y0)
                if drawn <= 0: break
                t = min(1.0, drawn / sl)
                ld.line([(x0, y0), (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)], fill=(*SAND, int(255 * 0.55 * min(1, p * 2))), width=max(1, int(round(k))))
                drawn -= sl
            s = 3 * k
            ld.rectangle([ax - s, ay - s, ax + s, ay + s], fill=(*YELLOW, int(255 * min(1, p * 2))))
            out = Image.alpha_composite(out, line)
            n = smooth(p * 1.4 - 0.4)
            if n > 0:
                tl = Image.new('RGBA', out.size, (0, 0, 0, 0)); td = ImageDraw.Draw(tl)
                tx = ex + 10 * k if dr > 0 else ex - 10 * k - tw
                base = ey - 6 * k - 0.14 * min(30, max(20, 0.018 * css_w)) * k
                # the soft dark halo behind the words (text-shadow), then the words
                sh = Image.new('RGBA', out.size, (0, 0, 0, 0))
                ImageDraw.Draw(sh).text((tx, base + (1 - n) * th), text, font=nf, fill=(7, 2, 14, int(255 * 0.85 * n)), anchor='ls')
                sh = sh.filter(ImageFilter.GaussianBlur(7 * k))
                out = Image.alpha_composite(out, Image.alpha_composite(sh, sh))
                td.text((tx, base + (1 - n) * th), text, font=nf, fill=(*SAND, int(255 * 0.94 * n)), anchor='ls')
                clip = Image.new('L', out.size, 0); ImageDraw.Draw(clip).rectangle([0, ey - 6 * k - th, out.size[0], ey - 6 * k], fill=255)
                tl.putalpha(Image.fromarray((np.asarray(tl.getchannel('A'), np.float32) * np.asarray(clip, np.float32) / 255).astype(np.uint8)))
                out = Image.alpha_composite(out, tl)
    return out.convert('RGB')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    css_w = 1440
    if '--css' in sys.argv: css_w = int(sys.argv[sys.argv.index('--css') + 1]); args = [a for a in args if a != str(css_w)]
    fdir, mdir, tpath, odir, first = args[:5]
    last = int(args[5]) if len(args) > 5 else int(first)
    track = json.load(open(tpath)); os.makedirs(odir, exist_ok=True)
    global BEATS                                          # main.js noteBeats(): from the track's two rests
    s4 = 'head' in track; sp = SPECS['s04' if s4 else 's03']
    if not s4:
        BEATS = [(track['b'] - 1 - 24, track['b'] - 1 + 8), (track['c'] - 1 - 26, track['c'] - 1 + 2)]
    for f in range(int(first), last + 1):
        fp = os.path.join(fdir, f'f_{f:04d}.webp')
        if not os.path.exists(fp): continue
        film = Image.open(fp).convert('RGB')
        film = film.resize((1920, 1080), Image.LANCZOS)
        mt = None
        for ext in ('png', 'webp'):
            mp = os.path.join(mdir, f'm_{f:04d}.{ext}')
            if os.path.exists(mp):
                im = Image.open(mp); mt = im.getchannel('A') if im.mode in ('RGBA', 'LA') else im.convert('L'); break
        T = track['frames'][f - track['from']] if 0 <= f - track['from'] < len(track['frames']) else None
        compose(film, mt, T, f - 1, css_w, sp, not s4).save(os.path.join(odir, f'c_{f:04d}.png'))
        print('composed', f)


if __name__ == '__main__':
    main()
