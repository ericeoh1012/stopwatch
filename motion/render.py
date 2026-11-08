"""피자 매장 EDA 시사점 — 30초 키네틱 타이포그래피 모션 그래픽 (코드 전용 렌더러)

실행: python3 render.py
필요: macOS `say`(Yuna 음성), Pretendard 폰트(~/Library/Fonts), Pillow, numpy, imageio-ffmpeg
출력: insight_brief.mp4 (1920x1080, 30fps, 30초, 한국어 내레이션)

매월 갱신할 때는 아래 VO / INSIGHTS 블록의 문구·숫자만 바꾸면 됩니다.
"""
import math
import os
import subprocess
import tempfile

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "insight_brief.mp4")
W, H, FPS, DUR = 1920, 1080, 30, 30.0
FONT_DIR = os.path.expanduser("~/Library/Fonts/")

# ── 팔레트 (보라 단일 액센트 + 뉴트럴) ─────────────────────────────
PURPLE = (120, 35, 220)
BRIGHT = (170, 115, 255)
DEEP = (24, 8, 48)
INK = (24, 20, 32)
GRAY = (112, 108, 124)
LINE = (228, 222, 238)
LIGHT = (240, 234, 250)
WHITE = (255, 255, 255)
LILAC = (196, 170, 245)

# ── 내레이션 (시작 시각, 문장) ────────────────────────────────────
VO = [
    (0.25, "피자 프랜차이즈 아홉 개 매장, 6년 치 실적에서 찾은 세 가지 시사점입니다."),
    (5.40, "첫째, 매출은 60% 늘었지만 주문은 제자리입니다. 성장은 가격이 만들었고, 인건비가 그 효과를 지웠습니다."),
    (13.20, "둘째, 자사앱 주문 비중은 31%로 다섯 배 늘었지만, 배달앱 수수료는 줄지 않았습니다."),
    (19.50, "셋째, 정규직 두 명 이하 소형점은 한 명만 빠져도 이익률이 3.7%까지 떨어집니다."),
    (25.90, "주문을 늘리고, 앱으로 전환하고, 소형점을 지키십시오."),
]
CUTS = [5.3, 13.1, 19.4, 25.7]  # 장면 전환 시각
TABS = ["성장의 질", "채널 전략", "인력 리스크"]

_fonts = {}


def F(weight, size):
    key = (weight, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(f"{FONT_DIR}Pretendard-{weight}.otf", size)
    return _fonts[key]


# ── 이징 ─────────────────────────────────────────────────────────
def clamp(x):
    return max(0.0, min(1.0, x))


def p(t, start, dur):
    return clamp((t - start) / dur)


def ease_out(x):  # expo
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def ease_io(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


# ── 텍스트 유틸 ──────────────────────────────────────────────────
_tcache = {}


def timg(text, font, color):
    key = (text, id(font), color)
    if key not in _tcache:
        asc, desc = font.getmetrics()
        w = max(1, math.ceil(font.getlength(text)))
        im = Image.new("RGBA", (w + 4, asc + desc), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), text, font=font, fill=color + (255,))
        _tcache[key] = im
    return _tcache[key]


def reveal(img, text, font, color, x, y, prog):
    """마스크 안에서 아래→위로 올라오는 키네틱 리빌."""
    if prog <= 0:
        return
    ti = timg(text, font, color)
    h = ti.height
    off = int(round((1 - ease_out(prog)) * h))
    if off >= h:
        return
    crop = ti.crop((0, 0, ti.width, h - off))
    img.paste(crop, (int(x), int(y + off)), crop)


def words(img, segs, font, x, y, t, t0, stagger=0.09, d=0.55):
    """segs: [(단어, 색)] — 단어 단위로 시차를 두고 리빌."""
    cx = x
    space = font.getlength(" ")
    for i, (w_, col) in enumerate(segs):
        reveal(img, w_, font, col, cx, y, p(t, t0 + i * stagger, d))
        cx += font.getlength(w_) + space
    return cx


def text(img, s, font, color, x, y, anchor="la"):
    ImageDraw.Draw(img).text((x, y), s, font=font, fill=color, anchor=anchor)


def bar(img, x, y, w, h, color):
    if w > 0.5:
        ImageDraw.Draw(img).rectangle([x, y, x + w, y + h], fill=color)


# ── 공통 크롬 (인사이트 장면) ─────────────────────────────────────
def chrome(img, t, idx, t0, t1):
    a = p(t, t0, 0.5)
    reveal(img, "PIZZA FRANCHISE  ·  DATA INSIGHT BRIEF", F("SemiBold", 22), GRAY, 120, 64, a)
    label = "9개 매장  ·  2020.01 – 2026.08"
    reveal(img, label, F("Medium", 22), GRAY, W - 120 - F("Medium", 22).getlength(label), 64, a)
    bar(img, 120, 112, (W - 240) * ease_out(p(t, t0, 0.8)), 1, LINE)
    # 하단 3단 진행바 — 세 시사점이 항상 보이도록
    seg_w, gap, y = (W - 240 - 2 * 24) / 3, 24, 980
    for i, name in enumerate(TABS):
        sx = 120 + i * (seg_w + gap)
        bar(img, sx, y, seg_w, 4, LINE)
        if i < idx:
            bar(img, sx, y, seg_w, 4, LILAC)
        elif i == idx:
            bar(img, sx, y, seg_w * clamp((t - t0) / (t1 - t0)), 4, PURPLE)
        col = PURPLE if i == idx else GRAY
        text(img, f"0{i + 1}  {name}", F("Bold" if i == idx else "Medium", 24), col, sx, y + 20)


def left_block(img, t, t0, n, kicker, l1, l2, support, sowhat, t_sup, t_sow):
    reveal(img, f"0{n}", F("Black", 170), PURPLE, 112, 150, p(t, t0 + 0.15, 0.6))
    reveal(img, kicker, F("SemiBold", 30), PURPLE, 124, 375, p(t, t0 + 0.35, 0.5))
    hf = F("Bold", 74)
    words(img, l1, hf, 120, 430, t, t0 + 0.5)
    words(img, l2, hf, 120, 530, t, t0 + 0.75)
    bar(img, 124, 650, 140 * ease_out(p(t, t0 + 1.1, 0.8)), 6, PURPLE)
    reveal(img, support, F("Medium", 32), GRAY, 124, 690, p(t, t_sup, 0.6))
    # So-what 박스
    k = ease_out(p(t, t_sow, 0.7))
    if k > 0:
        bw = 880
        bar(img, 120, 790, bw * k, 110, LIGHT)
        bar(img, 120, 790, 8, 110 * k, PURPLE)
        reveal(img, "SO WHAT", F("Bold", 22), PURPLE, 156, 808, p(t, t_sow + 0.15, 0.5))
        reveal(img, sowhat, F("Bold", 36), INK, 156, 840, p(t, t_sow + 0.25, 0.6))


# ── 장면 ─────────────────────────────────────────────────────────
def intro(img, t):
    img.paste(DEEP, (0, 0, W, H))
    # 배경의 큰 "3" — 천천히 떠오르는 키네틱 백드롭
    big = timg("3", F("Black", 900), (44, 18, 86))
    k = ease_out(p(t, 0.2, 2.5))
    img.paste(big, (1180, int(40 + 120 * (1 - k))), big)
    bar(img, 120, 300, 8, 360 * ease_out(p(t, 0.1, 0.9)), BRIGHT)
    reveal(img, "DATA INSIGHT BRIEF  ·  2026.11", F("SemiBold", 28), LILAC, 160, 300, p(t, 0.2, 0.6))
    hf = F("Bold", 92)
    words(img, [("피자", WHITE), ("프랜차이즈", WHITE), ("9개", BRIGHT), ("매장,", WHITE)], hf, 156, 360, t, 0.4)
    words(img, [("6년", BRIGHT), ("실적이", WHITE), ("말하는", WHITE)], hf, 156, 470, t, 1.6)
    words(img, [("3가지", BRIGHT), ("시사점", WHITE)], F("Black", 120), 156, 575, t, 3.0, stagger=0.15)
    for i, name in enumerate(TABS):
        x = 160 + i * 300
        q = p(t, 3.6 + i * 0.18, 0.5)
        bar(img, x, 790, 260 * ease_out(q), 2, LILAC)
        reveal(img, f"0{i + 1}  {name}", F("Medium", 28), LILAC, x, 808, q)


def ins1(img, t):
    t0, t1 = CUTS[0], CUTS[1]
    img.paste(WHITE, (0, 0, W, H))
    chrome(img, t, 0, t0, t1)
    left_block(img, t, t0, 1, "INSIGHT 01  ·  성장의 질",
               [("매출", INK), ("성장은", INK)], [("가격이", PURPLE), ("만들었다", INK)],
               "인건비율 24.5% → 29.0%, 규모 효과를 상쇄", "주문 수 회복과 인건비 생산성이 핵심 과제",
               t0 + 4.3, t0 + 5.6)
    rx = 1130
    # +60% 매출
    a = p(t, t0 + 1.0, 0.6)
    reveal(img, "월평균 매출  2020 → 2026", F("SemiBold", 28), GRAY, rx, 190, a)
    v = 60 * ease_io(p(t, t0 + 1.1, 1.2))
    reveal(img, f"+{v:.0f}%", F("Black", 190), PURPLE, rx - 8, 225, a)
    bar(img, rx, 470, 660 * ease_out(p(t, t0 + 1.1, 1.2)), 14, PURPLE)
    # +1% 주문
    b = p(t, t0 + 2.6, 0.6)
    reveal(img, "월 주문건수  2022 → 2026", F("SemiBold", 28), GRAY, rx, 540, b)
    v2 = 1 * ease_io(p(t, t0 + 2.7, 0.8))
    reveal(img, f"+{v2:.0f}%", F("Black", 190), INK, rx - 8, 575, b)
    bar(img, rx, 820, 660, 14, LINE)
    bar(img, rx, 820, 11 * ease_out(p(t, t0 + 2.7, 0.8)), 14, INK)
    reveal(img, "주문은 제자리", F("Bold", 26), INK, rx, 850, p(t, t0 + 3.2, 0.5))


def ins2(img, t):
    t0, t1 = CUTS[1], CUTS[2]
    img.paste(WHITE, (0, 0, W, H))
    chrome(img, t, 1, t0, t1)
    left_block(img, t, t0, 2, "INSIGHT 02  ·  채널 전략",
               [("자사앱은", INK), ("5배", PURPLE), ("성장,", INK)], [("수수료는", INK), ("그대로", PURPLE)],
               "플랫폼수수료 월 600만원 → 726만원 (2022 → 2026)", "앱 쿠폰은 배달앱 → 자사앱 전환 고객에 집중",
               t0 + 3.6, t0 + 4.8)
    rx, scale = 1130, 8.0

    def row(y, label, v0, v1, y0, y1, col, t_in):
        q = p(t, t_in, 0.6)
        reveal(img, label, F("SemiBold", 28), GRAY, rx, y, q)
        g = ease_io(p(t, t_in + 0.2, 1.2))
        # 기준년도 바
        reveal(img, y0, F("Medium", 22), GRAY, rx, y + 52, q)
        bar(img, rx + 70, y + 54, v0 * scale * ease_out(q), 26, LINE)
        reveal(img, f"{v0:.1f}%", F("SemiBold", 24), GRAY, rx + 82 + v0 * scale, y + 52, q)
        # 최근 바
        reveal(img, y1, F("Bold", 22), col, rx, y + 100, q)
        vv = v0 + (v1 - v0) * g
        bar(img, rx + 70, y + 98, vv * scale * ease_out(q), 54, col)
        reveal(img, f"{vv:.1f}%", F("Black", 64), col, rx + 86 + vv * scale, y + 88, q)

    row(200, "자사앱 주문비중", 5.6, 31.3, "2020", "2026", PURPLE, t0 + 1.0)
    row(520, "배달앱 경유 주문비중", 43.0, 42.4, "2022", "2026", INK, t0 + 2.4)
    reveal(img, "→ 변화 없음", F("Bold", 26), INK, rx, 700, p(t, t0 + 3.2, 0.5))


def ins3(img, t):
    t0, t1 = CUTS[2], CUTS[3]
    img.paste(WHITE, (0, 0, W, H))
    chrome(img, t, 2, t0, t1)
    left_block(img, t, t0, 3, "INSIGHT 03  ·  인력 리스크",
               [("정규직", INK), ("1명", PURPLE), ("이탈이", INK)], [("소형점", INK), ("이익을", INK), ("무너뜨린다", PURPLE)],
               "충장로·연동점 2026 이익률 13~14% (평균 17.4%)", "정규직 전환 지원금을 소형점에 우선 배분",
               t0 + 3.8, t0 + 4.8)
    rx = 1130
    a = p(t, t0 + 0.9, 0.6)
    reveal(img, "제주 연동점 영업이익률  ·  2026.04", F("SemiBold", 28), GRAY, rx, 190, a)
    v = 17.4 + (3.7 - 17.4) * ease_io(p(t, t0 + 1.3, 2.4))
    reveal(img, f"{v:.1f}%", F("Black", 200), PURPLE, rx - 8, 225, a)
    reveal(img, "정규직 3명 → 1.3명, 파트타임 12명으로 대체", F("Medium", 26), GRAY, rx, 480, p(t, t0 + 2.2, 0.5))
    # 비교 바 (평균 vs 연동점)
    s = 640 / 20.0
    q = p(t, t0 + 1.3, 0.6)
    reveal(img, "전 매장 평균", F("SemiBold", 24), GRAY, rx, 580, q)
    bar(img, rx, 620, 17.4 * s * ease_out(q), 40, LINE)
    reveal(img, "17.4%", F("Bold", 30), GRAY, rx + 17.4 * s + 14, 622, q)
    reveal(img, "연동점 2026.04", F("SemiBold", 24), PURPLE, rx, 700, q)
    w = (17.4 + (3.7 - 17.4) * ease_io(p(t, t0 + 1.3, 2.4))) * s
    bar(img, rx, 740, w * ease_out(q), 40, PURPLE)
    reveal(img, "−13.7%p", F("Black", 44), PURPLE, rx + 3.7 * s + 24, 734, p(t, t0 + 3.6, 0.5))


def outro(img, t):
    t0 = CUTS[3]
    img.paste(DEEP, (0, 0, W, H))
    reveal(img, "KEY TAKEAWAYS", F("SemiBold", 28), LILAC, 160, 250, p(t, t0 + 0.2, 0.5))
    bar(img, 160, 300, 1600 * ease_out(p(t, t0 + 0.2, 1.0)), 1, (70, 50, 110))
    rows = [("가격이 아닌", "주문", "으로 성장"), ("자사앱은", "배달앱 전환", "에 집중"), ("지원금은", "소형점", "부터")]
    starts = [t0 + 0.3, t0 + 1.4, t0 + 2.5]
    for i, (a_, b_, c_) in enumerate(rows):
        y = 350 + i * 170
        q = p(t, starts[i], 0.6)
        reveal(img, f"0{i + 1}", F("Black", 72), BRIGHT, 160, y, q)
        hf = F("Bold", 72)
        x = 330
        reveal(img, a_ + " ", hf, WHITE, x, y, p(t, starts[i] + 0.08, 0.6))
        x += hf.getlength(a_ + " ")
        reveal(img, b_, F("Black", 72), BRIGHT, x, y, p(t, starts[i] + 0.16, 0.6))
        x += F("Black", 72).getlength(b_)
        reveal(img, c_, hf, WHITE, x, y, p(t, starts[i] + 0.22, 0.6))
    reveal(img, "PIZZA FRANCHISE  ·  DATA INSIGHT BRIEF  ·  2026.11", F("Medium", 22), LILAC, 160, 940, p(t, t0 + 2.9, 0.6))


SCENES = [(0, intro), (CUTS[0], ins1), (CUTS[1], ins2), (CUTS[2], ins3), (CUTS[3], outro)]


def wipe(img, t):
    """장면 사이 보라 패널 와이프."""
    for c in CUTS:
        if c - 0.32 <= t < c:
            k = ease_io((t - (c - 0.32)) / 0.32)
            bar(img, 0, 0, W * k, H, PURPLE)
        elif c <= t < c + 0.32:
            k = ease_io((t - c) / 0.32)
            bar(img, W * k, 0, W * (1 - k), H, PURPLE)


def frame(t):
    img = Image.new("RGB", (W, H), WHITE)
    scene = [fn for s, fn in SCENES if t >= s][-1]
    scene(img, t)
    wipe(img, t)
    if t > DUR - 0.5:  # 마지막 페이드
        img = Image.blend(img, Image.new("RGB", (W, H), DEEP), clamp((t - (DUR - 0.5)) / 0.5))
    return img


def make_voice(tmp):
    paths = []
    for i, (_, line) in enumerate(VO):
        out = os.path.join(tmp, f"vo{i}.aiff")
        subprocess.run(["say", "-v", "Yuna", "-r", "185", "-o", out, line], check=True)
        paths.append(out)
    return paths


def main():
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        vo = make_voice(tmp)
        cmd = [ff, "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0"]
        for v in vo:
            cmd += ["-i", v]
        fc = ";".join(f"[{i + 1}]adelay={int(s * 1000)}|{int(s * 1000)},aresample=48000[a{i}]" for i, (s, _) in enumerate(VO))
        fc += ";" + "".join(f"[a{i}]" for i in range(len(VO))) + f"amix=inputs={len(VO)}:normalize=0,apad[a]"
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", str(DUR),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        n = int(DUR * FPS)
        for f in range(n):
            proc.stdin.write(frame(f / FPS).tobytes())
            if f % 150 == 0:
                print(f"  frame {f}/{n}")
        proc.stdin.close()
        proc.wait()
    print("done →", OUT)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--stills":  # 검수용 스틸 컷
        for s in sys.argv[2:]:
            frame(float(s)).save(os.path.join(HERE, f"still_{s}.png"))
    else:
        main()
