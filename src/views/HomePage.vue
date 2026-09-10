<template>
  <div class="home-page">
    <div class="bg-grid"></div>
    <div class="photo-backdrop" aria-hidden="true"></div>
    <div class="cinematic-light light-a"></div>
    <div class="cinematic-light light-b"></div>
    <div class="orbital orbital-a"></div>
    <div class="orbital orbital-b"></div>

    <section class="hero">
      <div class="hero-copy">
        <div class="eyebrow">
          <span class="signal-dot"></span>
          Forest Fire Emergency Intelligence Platform
        </div>
        <h1>
          星火智援
          <span>森林山火应急救灾智能系统</span>
        </h1>
        <div class="full-title">星火智援-——森林山火应急救灾智能系统</div>
        <p class="subtitle">
          面向山地森林火灾的监测、预测、决策与协同调度一体化演示平台
        </p>
        <div class="member-card">
          <span class="member-label">小组成员</span>
          <span class="member-names">施菲帆、邓玉洁、农青哲</span>
        </div>
      </div>

      <div class="earth-stage" aria-label="科技地球视觉">
        <div class="nebula nebula-blue"></div>
        <div class="nebula nebula-fire"></div>
        <div class="earth-glow"></div>
        <div class="orbit orbit-one"></div>
        <div class="orbit orbit-two"></div>
        <div class="satellite satellite-a"></div>
        <div class="satellite satellite-b"></div>
        <div class="earth">
          <div class="photo-shade"></div>
          <div class="terminator-glow"></div>
          <div class="aurora aurora-a"></div>
          <div class="aurora aurora-b"></div>
          <div class="data-arc data-arc-a"></div>
          <div class="data-arc data-arc-b"></div>
          <div class="data-arc data-arc-c"></div>
          <div class="heat-core"></div>
          <div class="heat-ripple ripple-a"></div>
          <div class="heat-ripple ripple-b"></div>
          <div class="scan-ring"></div>
          <div class="node node-a"></div>
          <div class="node node-b"></div>
          <div class="city-lights"></div>
        </div>
        <div class="data-label label-a">IGNITION</div>
        <div class="data-label label-b">FORECAST</div>
        <div class="data-panel panel-a">
          <span>LIVE RISK</span>
          <strong>HIGH</strong>
        </div>
        <div class="data-panel panel-b">
          <span>RESPONSE</span>
          <strong>READY</strong>
        </div>
        <div class="star-field"></div>
      </div>
    </section>

    <section class="feature-strip">
      <div class="feature-item">
        <span class="feature-k">01</span>
        <span class="feature-v">火点监测</span>
      </div>
      <div class="feature-item">
        <span class="feature-k">02</span>
        <span class="feature-v">蔓延预测</span>
      </div>
      <div class="feature-item">
        <span class="feature-k">03</span>
        <span class="feature-v">Agent 决策</span>
      </div>
      <div class="feature-item">
        <span class="feature-k">04</span>
        <span class="feature-v">救援调度</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.home-page {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  color: #e2e8f0;
  background:
    radial-gradient(circle at 72% 48%, rgba(56, 189, 248, 0.18), transparent 34%),
    radial-gradient(circle at 22% 28%, rgba(249, 115, 22, 0.15), transparent 28%),
    linear-gradient(135deg, #070b14 0%, #101827 48%, #07111f 100%);
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(circle at 50% 50%, black, transparent 76%);
}

.photo-backdrop {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, rgba(7, 11, 20, 0.98) 0%, rgba(7, 11, 20, 0.9) 30%, rgba(7, 11, 20, 0.48) 56%, rgba(7, 11, 20, 0.16) 100%),
    linear-gradient(180deg, rgba(7, 11, 20, 0.48) 0%, rgba(7, 11, 20, 0.12) 38%, rgba(7, 11, 20, 0.24) 100%),
    radial-gradient(ellipse at 22% 48%, rgba(249, 115, 22, 0.14), transparent 38%),
    radial-gradient(ellipse at 76% 42%, rgba(56, 189, 248, 0.12), transparent 42%),
    url('../assets/home-fire-rescue-bg.png');
  /* 渐变遮罩铺满整屏，只有照片本身右侧 contain，避免多层背景共同缩放后在页面中线形成直切边。 */
  background-size:
    100% 100%,
    100% 100%,
    100% 100%,
    100% 100%,
    cover;
  background-repeat: no-repeat;
  background-position:
    center,
    center,
    center,
    center,
    center center;
  opacity: 1;
  filter: saturate(1.22) contrast(1.12) brightness(0.96);
  /* 拉长左侧羽化区，让照片边界自然融入底色。 */
  mask-image:
    radial-gradient(ellipse at 78% 50%, black 0%, rgba(0,0,0,0.92) 44%, rgba(0,0,0,0.42) 70%, transparent 100%),
    /* 右侧照片最左侧透明度为 0，从左到右逐渐显现，避免图片左边界生硬露出。 */
    linear-gradient(90deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0) 22%, rgba(0,0,0,0.28) 52%, black 100%);
  mask-composite: intersect;
}

/* 覆盖旧遮罩：照片完整铺满首屏，只靠深色渐变融合，不再出现左右割裂的裁切边界。 */
.photo-backdrop {
  mask-image: none;
  mask-composite: initial;
}

.photo-backdrop::before,
.photo-backdrop::after {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.photo-backdrop::before {
  background:
    linear-gradient(90deg, rgba(7, 11, 20, 0.72) 0%, rgba(7, 11, 20, 0.28) 42%, transparent 78%),
    linear-gradient(180deg, rgba(7, 11, 20, 0.48) 0%, transparent 32%, transparent 100%),
    radial-gradient(circle at 78% 28%, rgba(56, 189, 248, 0.28), transparent 34%),
    radial-gradient(circle at 48% 66%, rgba(249, 115, 22, 0.2), transparent 30%);
  mix-blend-mode: screen;
}

.photo-backdrop::after {
  background:
    repeating-linear-gradient(90deg, rgba(125, 211, 252, 0.08) 0 1px, transparent 1px 74px),
    repeating-linear-gradient(0deg, rgba(125, 211, 252, 0.06) 0 1px, transparent 1px 58px);
  opacity: 0.35;
  mix-blend-mode: screen;
}

.cinematic-light {
  position: absolute;
  pointer-events: none;
  mix-blend-mode: screen;
}

.light-a {
  width: 54vw;
  height: 36vh;
  left: -14vw;
  top: 8vh;
  background: linear-gradient(105deg, rgba(59,130,246,0.22), transparent 68%);
  filter: blur(18px);
  transform: rotate(-8deg);
}

.light-b {
  width: 44vw;
  height: 30vh;
  right: -12vw;
  bottom: 4vh;
  background: linear-gradient(285deg, rgba(249,115,22,0.18), transparent 70%);
  filter: blur(20px);
  transform: rotate(8deg);
}

.orbital {
  position: absolute;
  border: 1px solid rgba(96, 165, 250, 0.24);
  border-radius: 50%;
  transform: rotate(-18deg);
}

.orbital-a {
  width: min(66vw, 900px);
  height: min(28vw, 380px);
  right: 4vw;
  top: 18vh;
}

.orbital-b {
  width: min(52vw, 720px);
  height: min(22vw, 300px);
  right: 10vw;
  top: 28vh;
  border-color: rgba(249, 115, 22, 0.22);
}

.hero {
  position: relative;
  z-index: 1;
  height: calc(100% - 88px);
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(420px, 0.95fr) minmax(360px, 1.05fr);
  align-items: center;
  gap: clamp(24px, 5vw, 88px);
  padding: clamp(28px, 5vh, 64px) clamp(36px, 6vw, 110px) 0;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  gap: clamp(16px, 2.5vh, 28px);
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: fit-content;
  padding: 9px 14px;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 999px;
  color: #93c5fd;
  background: rgba(15, 23, 42, 0.58);
  box-shadow: 0 0 24px rgba(59, 130, 246, 0.12);
  font-size: clamp(11px, 0.78vw, 14px);
}

.signal-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f97316;
  box-shadow: 0 0 14px #f97316;
}

h1 {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: clamp(56px, 6vw, 96px);
  line-height: 0.95;
  letter-spacing: 0;
  color: #f8fafc;
  text-shadow: 0 0 28px rgba(96, 165, 250, 0.22);
}

h1 span {
  font-size: clamp(24px, 2.6vw, 42px);
  color: #f97316;
}

.subtitle {
  margin: 0;
  max-width: 720px;
  color: #94a3b8;
  font-size: clamp(15px, 1.1vw, 20px);
  line-height: 1.8;
}

.full-title {
  color: #bfdbfe;
  font-size: clamp(13px, 0.95vw, 16px);
  letter-spacing: 0;
}

.member-card {
  display: flex;
  align-items: center;
  gap: 18px;
  width: fit-content;
  padding: 16px 20px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.62);
  backdrop-filter: blur(16px);
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.26);
}

.member-label {
  color: #60a5fa;
  font-size: 13px;
}

.member-names {
  color: #f8fafc;
  font-size: clamp(16px, 1.2vw, 22px);
  font-weight: 700;
}

.earth-stage {
  position: relative;
  display: none;
  place-items: center;
  min-height: 520px;
  perspective: 900px;
  isolation: isolate;
}

.nebula {
  position: absolute;
  width: min(48vw, 720px);
  aspect-ratio: 1.35;
  border-radius: 50%;
  filter: blur(26px);
  opacity: 0.72;
  mix-blend-mode: screen;
}

.nebula-blue {
  background:
    radial-gradient(ellipse at 54% 44%, rgba(59,130,246,0.24), transparent 54%),
    radial-gradient(ellipse at 35% 64%, rgba(14,165,233,0.2), transparent 48%);
  transform: rotate(-12deg);
}

.nebula-fire {
  width: min(42vw, 620px);
  background:
    radial-gradient(ellipse at 58% 62%, rgba(249,115,22,0.22), transparent 45%),
    radial-gradient(ellipse at 48% 42%, rgba(239,68,68,0.12), transparent 36%);
  transform: rotate(16deg);
}

.earth-glow {
  position: absolute;
  width: min(44vw, 660px);
  aspect-ratio: 1;
  border-radius: 50%;
  background:
    radial-gradient(circle, rgba(125, 211, 252, 0.24), transparent 54%),
    radial-gradient(circle at 56% 58%, rgba(249, 115, 22, 0.12), transparent 38%);
  filter: blur(22px);
}

.orbit {
  position: absolute;
  border: 1px solid rgba(147, 197, 253, 0.28);
  border-radius: 50%;
  transform-style: preserve-3d;
}

.orbit-one {
  width: min(46vw, 680px);
  height: min(18vw, 260px);
  transform: rotateZ(-24deg) rotateX(58deg);
  box-shadow: 0 0 28px rgba(59, 130, 246, 0.18);
}

.orbit-two {
  width: min(39vw, 580px);
  height: min(14vw, 210px);
  transform: rotateZ(18deg) rotateX(66deg);
  border-color: rgba(249, 115, 22, 0.26);
}

.satellite {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e0f2fe;
  box-shadow: 0 0 16px #38bdf8;
}

.satellite-a {
  right: 18%;
  top: 30%;
}

.satellite-b {
  right: 34%;
  bottom: 18%;
  background: #fed7aa;
  box-shadow: 0 0 16px #f97316;
}

.star-field {
  position: absolute;
  inset: 6% 2%;
  z-index: -1;
  background:
    radial-gradient(circle at 18% 24%, rgba(255,255,255,0.72) 0 1px, transparent 2px),
    radial-gradient(circle at 82% 18%, rgba(147,197,253,0.7) 0 1px, transparent 2px),
    radial-gradient(circle at 74% 72%, rgba(255,255,255,0.62) 0 1px, transparent 2px),
    radial-gradient(circle at 28% 82%, rgba(125,211,252,0.55) 0 1px, transparent 2px),
    radial-gradient(circle at 58% 10%, rgba(255,255,255,0.5) 0 1px, transparent 2px),
    radial-gradient(circle at 44% 30%, rgba(255,255,255,0.38) 0 1px, transparent 2px),
    radial-gradient(circle at 90% 48%, rgba(147,197,253,0.52) 0 1px, transparent 2px),
    radial-gradient(circle at 10% 58%, rgba(249,115,22,0.42) 0 1px, transparent 2px);
  opacity: 0.55;
}

.earth {
  position: relative;
  width: min(39vw, 590px);
  aspect-ratio: 1;
  border-radius: 50%;
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.28);
  background:
    linear-gradient(116deg, rgba(255,255,255,0.14), transparent 28%, rgba(0,0,0,0.04) 48%, rgba(0,0,0,0.58) 100%),
    url('../assets/earth-photo-full-disk.jpg');
  background-size: 118% 118%;
  background-position: 50% 50%;
  box-shadow:
    inset -42px -48px 96px rgba(0, 0, 0, 0.58),
    inset 18px 14px 38px rgba(255, 255, 255, 0.08),
    0 0 70px rgba(59, 130, 246, 0.34),
    0 0 150px rgba(14, 165, 233, 0.16),
    0 34px 80px rgba(0, 0, 0, 0.42);
}

.earth::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 28% 22%, rgba(255, 255, 255, 0.2), transparent 16%),
    linear-gradient(110deg, transparent 0 46%, rgba(255,255,255,0.11) 49%, transparent 55%),
    radial-gradient(circle at 70% 60%, transparent 0 34%, rgba(0,0,0,0.42) 72%);
  pointer-events: none;
}

.photo-shade {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  box-shadow:
    inset 0 0 34px rgba(125, 211, 252, 0.18),
    inset -54px -48px 90px rgba(0, 0, 0, 0.42);
}

.terminator-glow {
  position: absolute;
  inset: -1%;
  border-radius: 50%;
  background:
    radial-gradient(circle at 22% 18%, rgba(255,255,255,0.2), transparent 18%),
    linear-gradient(125deg, rgba(255,255,255,0.16), transparent 32%, rgba(0,0,0,0.12) 52%, rgba(0,0,0,0.52));
  mix-blend-mode: screen;
}

.aurora {
  position: absolute;
  left: 14%;
  right: 18%;
  height: 16%;
  border-radius: 50%;
  filter: blur(8px);
  opacity: 0.5;
  transform: rotate(-14deg);
  mix-blend-mode: screen;
}

.aurora-a {
  top: 24%;
  background: linear-gradient(90deg, transparent, rgba(56,189,248,0.5), rgba(34,197,94,0.26), transparent);
}

.aurora-b {
  top: 34%;
  left: 22%;
  right: 26%;
  height: 11%;
  background: linear-gradient(90deg, transparent, rgba(147,197,253,0.28), rgba(249,115,22,0.2), transparent);
}

.data-arc {
  position: absolute;
  border-radius: 50%;
  border: 1px solid transparent;
  border-top-color: rgba(125, 211, 252, 0.62);
  border-right-color: rgba(125, 211, 252, 0.16);
  filter: drop-shadow(0 0 8px rgba(56,189,248,0.4));
  pointer-events: none;
}

.data-arc-a {
  width: 54%;
  height: 30%;
  left: 20%;
  top: 22%;
  transform: rotate(18deg);
}

.data-arc-b {
  width: 62%;
  height: 42%;
  left: 17%;
  top: 35%;
  transform: rotate(-22deg);
  border-top-color: rgba(249,115,22,0.58);
}

.data-arc-c {
  width: 34%;
  height: 22%;
  left: 44%;
  top: 48%;
  transform: rotate(34deg);
}

.earth-atmosphere {
  position: absolute;
  inset: -2%;
  border-radius: 50%;
  border: 2px solid rgba(125, 211, 252, 0.34);
  box-shadow:
    inset 0 0 30px rgba(56, 189, 248, 0.22),
    0 0 36px rgba(125, 211, 252, 0.26);
}

.earth-ocean {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(ellipse at 40% 42%, rgba(125, 211, 252, 0.14), transparent 35%),
    radial-gradient(circle at 68% 64%, rgba(0, 0, 0, 0.28), transparent 42%);
  mix-blend-mode: screen;
}

.earth-clouds {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  opacity: 0.34;
  background:
    radial-gradient(ellipse at 35% 28%, rgba(255,255,255,0.78), transparent 15%),
    radial-gradient(ellipse at 58% 42%, rgba(255,255,255,0.42), transparent 18%),
    radial-gradient(ellipse at 43% 62%, rgba(255,255,255,0.5), transparent 14%),
    repeating-linear-gradient(12deg, transparent 0 30px, rgba(255,255,255,0.16) 31px 34px, transparent 35px 62px);
  filter: blur(1px);
  mix-blend-mode: screen;
}

.land {
  position: absolute;
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.58), rgba(21, 128, 61, 0.22));
  border: 1px solid rgba(187, 247, 208, 0.18);
  opacity: 0;
  filter: drop-shadow(0 0 8px rgba(34, 197, 94, 0.2));
}

.land-a {
  width: 28%;
  height: 20%;
  left: 24%;
  top: 25%;
  border-radius: 58% 32% 44% 38%;
  transform: rotate(-24deg);
}

.land-b {
  width: 30%;
  height: 28%;
  left: 48%;
  top: 34%;
  border-radius: 32% 64% 38% 52%;
  transform: rotate(18deg);
}

.land-c {
  width: 18%;
  height: 26%;
  left: 34%;
  top: 53%;
  border-radius: 46% 28% 62% 35%;
  transform: rotate(10deg);
}

.land-d {
  width: 20%;
  height: 12%;
  left: 58%;
  top: 64%;
  border-radius: 52% 38% 48% 32%;
  transform: rotate(-8deg);
  background: linear-gradient(135deg, rgba(132, 204, 22, 0.45), rgba(34, 197, 94, 0.16));
}

.earth-lines {
  position: absolute;
  inset: 8%;
  border-radius: 50%;
  background:
    repeating-linear-gradient(0deg, transparent 0 22px, rgba(147, 197, 253, 0.14) 23px 24px),
    repeating-linear-gradient(90deg, transparent 0 28px, rgba(147, 197, 253, 0.12) 29px 30px);
  mask-image: radial-gradient(circle, black 58%, transparent 70%);
}

.longitude,
.latitude {
  position: absolute;
  border: 1px solid rgba(191, 219, 254, 0.22);
  border-radius: 50%;
  pointer-events: none;
}

.longitude-a {
  inset: 8% 36%;
}

.longitude-b {
  inset: 8% 24%;
  transform: rotate(22deg);
}

.latitude-a {
  left: 8%;
  right: 8%;
  top: 31%;
  height: 18%;
}

.latitude-b {
  left: 10%;
  right: 10%;
  bottom: 24%;
  height: 20%;
  transform: rotate(-8deg);
}

.fire-front {
  position: absolute;
  border: 2px solid #fb923c;
  border-radius: 50%;
  box-shadow: 0 0 18px #f97316;
}

.front-a {
  width: 26%;
  height: 16%;
  left: 42%;
  top: 46%;
  transform: rotate(-18deg);
}

.front-b {
  width: 34%;
  height: 20%;
  left: 34%;
  top: 42%;
  border-color: rgba(248, 113, 113, 0.72);
  transform: rotate(-10deg);
}

.heat-core {
  position: absolute;
  width: 7%;
  height: 7%;
  left: 51%;
  top: 54%;
  border-radius: 50%;
  background: radial-gradient(circle, #fff7ad 0 14%, #fb923c 38%, rgba(239, 68, 68, 0.18) 66%, transparent 72%);
  box-shadow: 0 0 24px #f97316;
}

.heat-ripple {
  position: absolute;
  left: 48%;
  top: 51%;
  border-radius: 50%;
  border: 1px solid rgba(249, 115, 22, 0.72);
  transform: rotate(-12deg);
  box-shadow: 0 0 18px rgba(249, 115, 22, 0.36);
}

.ripple-a {
  width: 18%;
  height: 10%;
}

.ripple-b {
  width: 26%;
  height: 15%;
  left: 44%;
  top: 48%;
  border-color: rgba(248, 113, 113, 0.42);
}

.scan-sweep {
  position: absolute;
  inset: 14%;
  border-radius: 50%;
  background: conic-gradient(from 246deg, rgba(56,189,248,0.34), transparent 24%, transparent);
  mix-blend-mode: screen;
  transform: rotate(-18deg);
  mask-image: radial-gradient(circle, transparent 0 28%, black 30% 70%, transparent 72%);
}

.scan-ring {
  position: absolute;
  inset: 12%;
  border: 1px solid rgba(125, 211, 252, 0.38);
  border-radius: 50%;
  box-shadow: 0 0 20px rgba(96, 165, 250, 0.18);
}

.city-lights {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 54% 54%, rgba(250,204,21,0.8) 0 1px, transparent 2px),
    radial-gradient(circle at 57% 57%, rgba(251,146,60,0.7) 0 1px, transparent 2px),
    radial-gradient(circle at 50% 61%, rgba(250,204,21,0.55) 0 1px, transparent 2px),
    radial-gradient(circle at 63% 50%, rgba(250,204,21,0.5) 0 1px, transparent 2px);
  mix-blend-mode: screen;
  opacity: 0.78;
}

.node {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f97316;
  box-shadow: 0 0 16px #f97316;
}

.node-a { left: 48%; top: 42%; }
.node-b { left: 58%; top: 54%; background: #38bdf8; box-shadow: 0 0 16px #38bdf8; }

.data-label {
  position: absolute;
  padding: 5px 8px;
  border: 1px solid rgba(125, 211, 252, 0.25);
  border-radius: 4px;
  color: #bfdbfe;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(10px);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  box-shadow: 0 0 18px rgba(56,189,248,0.16);
}

.data-panel {
  position: absolute;
  min-width: 96px;
  padding: 10px 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(15,23,42,0.78), rgba(15,23,42,0.32)),
    radial-gradient(circle at 20% 20%, rgba(96,165,250,0.16), transparent 55%);
  backdrop-filter: blur(14px);
  box-shadow: 0 18px 44px rgba(0,0,0,0.28);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.data-panel span {
  font-size: 9px;
  color: #93c5fd;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.data-panel strong {
  color: #f8fafc;
  font-size: 17px;
}

.panel-a {
  left: 7%;
  bottom: 29%;
  border-color: rgba(249, 115, 22, 0.2);
}

.panel-a strong {
  color: #fb923c;
}

.panel-b {
  right: 9%;
  bottom: 23%;
}

.label-a {
  right: 20%;
  top: 42%;
  color: #fed7aa;
  border-color: rgba(249, 115, 22, 0.28);
}

.label-b {
  right: 34%;
  top: 28%;
}

.feature-strip {
  position: relative;
  z-index: 1;
  height: 88px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  margin: 0 clamp(36px, 6vw, 110px) clamp(18px, 3vh, 32px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.68);
  backdrop-filter: blur(16px);
}

.feature-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.feature-k {
  color: #f97316;
  font-size: 13px;
  font-weight: 800;
}

.feature-v {
  color: #cbd5e1;
  font-size: clamp(13px, 0.95vw, 17px);
}

@media (max-width: 1100px) {
  .hero {
    grid-template-columns: 1fr;
    gap: 12px;
    padding-top: 24px;
  }

  .earth-stage {
    min-height: 300px;
  }

  .earth {
    width: min(54vw, 360px);
  }
}
</style>
