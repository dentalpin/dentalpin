<script setup lang="ts">
type SceneChapter = {
  eyebrow: string
  title: string
  body: string
  cardLabel: string
  cardTitle: string
  cardBody: string
  cardMark: string
}

const props = defineProps<{
  chapters: SceneChapter[]
  scrollLabel: string
}>()

const story = ref<HTMLElement | null>(null)
const stage = ref<HTMLElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const progress = ref(0)
const webglReady = ref(false)
const reducedMotion = ref(false)

const storyStep = computed(() => Math.min(
  props.chapters.length,
  Math.floor(progress.value * (props.chapters.length + 1))
))
const activeChapter = computed(() => props.chapters[storyStep.value - 1])

let THREE: typeof import('three') | null = null
let renderer: import('three').WebGLRenderer | null = null
let scene: import('three').Scene | null = null
let camera: import('three').PerspectiveCamera | null = null
let tooth: import('three').Group | null = null
let orbit: import('three').Group | null = null
let inspectionRing: import('three').Mesh | null = null
let planRing: import('three').Mesh | null = null
let markers: import('three').Mesh[] = []
let resizeObserver: ResizeObserver | null = null
let visibilityObserver: IntersectionObserver | null = null
let motionQuery: MediaQueryList | null = null
let frame = 0
let isVisible = true
let isMobile = false

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function smoothstep(a: number, b: number, value: number) {
  const amount = clamp((value - a) / (b - a), 0, 1)
  return amount * amount * (3 - 2 * amount)
}

async function addTooth() {
  const three = THREE
  if (!three || !scene) return

  const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js')
  const gltf = await new GLTFLoader().loadAsync('/models/dentum-maxillary-first-molar.glb')
  const group = new three.Group()
  const model = gltf.scene
  model.rotation.x = Math.PI
  model.updateMatrixWorld(true)

  const originalBounds = new three.Box3().setFromObject(model)
  const originalHeight = originalBounds.getSize(new three.Vector3()).y
  const targetHeight = isMobile ? 3.05 : 3.28
  model.scale.setScalar(targetHeight / Math.max(originalHeight, 0.001))
  model.updateMatrixWorld(true)

  const bounds = new three.Box3().setFromObject(model)
  model.position.sub(bounds.getCenter(new three.Vector3()))
  group.position.set(isMobile ? 0 : 1.02, -0.03, 0)
  group.add(model)
  scene.add(group)
  scene.updateMatrixWorld(true)

  const modelBounds = new three.Box3().setFromObject(model)
  const verticalRange = Math.max(modelBounds.max.y - modelBounds.min.y, 0.001)
  const rootTone = new three.Color('#decdaa')
  const crownTone = new three.Color('#fffdf6')
  const vertex = new three.Vector3()
  const vertexColor = new three.Color()

  model.traverse((object) => {
    if (!(object instanceof three.Mesh)) return
    const geometry = object.geometry
    const positions = geometry.getAttribute('position')
    const colors = new Float32Array(positions.count * 3)

    for (let index = 0; index < positions.count; index++) {
      vertex.fromBufferAttribute(positions, index).applyMatrix4(object.matrixWorld)
      const enamel = smoothstep(
        modelBounds.min.y + verticalRange * 0.46,
        modelBounds.min.y + verticalRange * 0.54,
        vertex.y
      )
      vertexColor.copy(rootTone).lerp(crownTone, enamel)
      colors[index * 3] = vertexColor.r
      colors[index * 3 + 1] = vertexColor.g
      colors[index * 3 + 2] = vertexColor.b
    }

    geometry.setAttribute('color', new three.Float32BufferAttribute(colors, 3))
    geometry.computeVertexNormals()
    object.material = new three.MeshPhysicalMaterial({
      color: '#ffffff',
      vertexColors: true,
      roughness: 0.29,
      clearcoat: 0.46,
      clearcoatRoughness: 0.24,
      sheen: 0.16,
      sheenColor: '#d9e9e6'
    })
    object.castShadow = true
    object.receiveShadow = true
  })

  tooth = group
}

async function createScene() {
  const three = THREE
  if (!three || !canvas.value || !stage.value) return
  try {
    const width = stage.value.clientWidth
    const height = stage.value.clientHeight
    const pixelRatio = Math.min(window.devicePixelRatio || 1, isMobile ? 1.35 : 1.8)

    scene = new three.Scene()
    camera = new three.PerspectiveCamera(32, width / Math.max(height, 1), 0.1, 60)
    camera.position.set(isMobile ? 0 : 1.02, 0.18, isMobile ? 7.3 : 8)

    renderer = new three.WebGLRenderer({
      canvas: canvas.value,
      alpha: true,
      antialias: !isMobile,
      powerPreference: 'low-power',
      failIfMajorPerformanceCaveat: false
    })
    renderer.setPixelRatio(pixelRatio)
    renderer.setSize(width, height, false)
    renderer.outputColorSpace = three.SRGBColorSpace
    renderer.toneMapping = three.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.12

    scene.add(new three.HemisphereLight('#fffdf7', '#b8cfd0', 2.25))
    const key = new three.DirectionalLight('#fff9eb', 3.6)
    key.position.set(-3.5, 5, 6)
    scene.add(key)
    const rim = new three.DirectionalLight('#61d1df', 2.7)
    rim.position.set(4, 1.5, -3)
    scene.add(rim)
    const fill = new three.PointLight('#a5e6e3', 65, 12, 2)
    fill.position.set(-3.2, -1.5, 3.5)
    scene.add(fill)

    await addTooth()

    orbit = new three.Group()
    orbit.position.set(isMobile ? 0 : 1.02, -0.04, -0.06)
    scene.add(orbit)
    const halo = new three.Mesh(
      new three.TorusGeometry(1.74, 0.008, 8, 160),
      new three.MeshBasicMaterial({ color: '#64c6d2', transparent: true, opacity: 0.4 })
    )
    halo.rotation.set(0.72, 0.32, -0.3)
    orbit.add(halo)

    const halo2 = new three.Mesh(
      new three.TorusGeometry(1.94, 0.005, 8, 160),
      new three.MeshBasicMaterial({ color: '#89c5c4', transparent: true, opacity: 0.24 })
    )
    halo2.rotation.set(0.95, -0.38, 0.55)
    orbit.add(halo2)

    inspectionRing = new three.Mesh(
      new three.TorusGeometry(0.92, 0.012, 8, 120),
      new three.MeshBasicMaterial({ color: '#078d9a', transparent: true, opacity: 0.72 })
    )
    inspectionRing.position.set(0.18, 0.57, 0.38)
    inspectionRing.rotation.set(1.16, 0.23, 0.12)
    inspectionRing.visible = false
    orbit.add(inspectionRing)

    planRing = new three.Mesh(
      new three.TorusGeometry(1.24, 0.013, 8, 120),
      new three.MeshBasicMaterial({ color: '#54b8b5', transparent: true, opacity: 0.62 })
    )
    planRing.position.set(-0.13, 0.12, 0)
    planRing.rotation.set(0.34, 0.7, -0.24)
    planRing.visible = false
    orbit.add(planRing)

    const markerMaterial = new three.MeshBasicMaterial({ color: '#088c99' })
    const markerPositions: [number, number, number][] = [
      [0.2, 0.62, 0.58],
      [-0.42, 0.27, 0.55],
      [0.47, 0.22, 0.51]
    ]
    markers = []
    for (let index = 0; index < markerPositions.length; index++) {
      const position = markerPositions[index]!
      const marker = new three.Mesh(
        new three.SphereGeometry(index === 0 ? 0.055 : 0.035, 20, 14),
        markerMaterial
      )
      marker.position.set(...position)
      marker.visible = false
      orbit.add(marker)
      markers.push(marker)
    }

    syncScene()
    webglReady.value = true
  } catch {
    webglReady.value = false
    renderer?.dispose()
    renderer = null
  }
}

function syncScroll() {
  if (!story.value) return
  const storyTop = story.value.getBoundingClientRect().top + window.scrollY
  const storyRange = Math.max(1, story.value.offsetHeight - window.innerHeight)
  progress.value = clamp((window.scrollY - storyTop) / storyRange, 0, 1)
}

function syncScene() {
  if (!scene || !camera || !renderer || !tooth || !orbit) return

  const amount = progress.value
  const step = amount * (props.chapters.length + 1)
  const reduced = reducedMotion.value
  const baseX = isMobile ? 0 : 1.02
  const drift = reduced ? 0 : Math.sin(amount * Math.PI * 2) * (isMobile ? 0.07 : 0.18)
  const cameraLift = reduced ? 0 : Math.sin(amount * Math.PI) * 0.22

  tooth.position.x = baseX + drift
  tooth.rotation.y = reduced ? -0.2 : -0.18 + amount * Math.PI * 1.7
  tooth.rotation.x = reduced ? 0.03 : 0.03 + Math.sin(amount * Math.PI * 2) * 0.12
  tooth.rotation.z = reduced ? 0 : Math.sin(amount * Math.PI * 2) * 0.06
  tooth.scale.setScalar(isMobile ? 0.91 : 1)

  orbit.position.x = baseX + drift
  orbit.rotation.y = reduced ? 0 : -amount * 1.15
  orbit.rotation.z = reduced ? 0 : Math.sin(amount * Math.PI) * 0.06
  if (inspectionRing) inspectionRing.visible = step > 0.8
  if (planRing) planRing.visible = step > 1.75
  markers.forEach((marker, index) => {
    marker.visible = step > index + 0.8
    marker.scale.setScalar(0.8 + (reduced ? 0 : Math.sin(amount * 12 + index) * 0.1))
  })

  camera.position.x = baseX + drift * 0.58
  camera.position.y = 0.18 + cameraLift
  camera.position.z = (isMobile ? 7.3 : 8) - (reduced ? 0 : Math.sin(amount * Math.PI) * 0.42)
  camera.lookAt(baseX + drift * 0.25, 0.02, 0)
  renderer.render(scene, camera)
}

function scheduleFrame() {
  if (frame || !import.meta.client) return
  frame = window.requestAnimationFrame(() => {
    frame = 0
    syncScroll()
    if (isVisible) syncScene()
  })
}

function resizeScene() {
  if (!renderer || !camera || !stage.value) return
  const width = Math.max(1, stage.value.clientWidth)
  const height = Math.max(1, stage.value.clientHeight)
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.fov = isMobile ? 35 : 32
  camera.updateProjectionMatrix()
  scheduleFrame()
}

function onMotionPreferenceChange(event: MediaQueryListEvent) {
  reducedMotion.value = event.matches
  scheduleFrame()
}

onMounted(async () => {
  isMobile = window.matchMedia('(max-width: 760px), (pointer: coarse)').matches
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion.value = motionQuery.matches
  motionQuery.addEventListener('change', onMotionPreferenceChange)
  window.addEventListener('scroll', scheduleFrame, { passive: true })
  window.addEventListener('resize', resizeScene, { passive: true })

  resizeObserver = new ResizeObserver(resizeScene)
  if (stage.value) resizeObserver.observe(stage.value)
  visibilityObserver = new IntersectionObserver((entries) => {
    const entry = entries[0]
    if (!entry) return
    isVisible = entry.isIntersecting
    if (isVisible) scheduleFrame()
  }, { rootMargin: '120px 0px' })
  if (story.value) visibilityObserver.observe(story.value)

  syncScroll()
  try {
    THREE = await import('three')
    await createScene()
    resizeScene()
  } catch {
    webglReady.value = false
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', scheduleFrame)
  window.removeEventListener('resize', resizeScene)
  motionQuery?.removeEventListener('change', onMotionPreferenceChange)
  resizeObserver?.disconnect()
  visibilityObserver?.disconnect()
  if (frame) window.cancelAnimationFrame(frame)
  const three = THREE
  if (scene && three) {
    scene.traverse((object) => {
      if (!(object instanceof three.Mesh)) return
      object.geometry.dispose()
      const material = object.material
      if (Array.isArray(material)) material.forEach(item => item.dispose())
      else material.dispose()
    })
  }
  renderer?.dispose()
  renderer = null
  scene = null
  camera = null
  tooth = null
  orbit = null
})
</script>

<template>
  <div
    ref="story"
    class="dentum-story"
  >
    <div
      ref="stage"
      class="scene-stage"
    >
      <div class="scene-stage__wash" />
      <canvas
        ref="canvas"
        class="scene-canvas"
        aria-hidden="true"
      />

      <svg
        v-if="!webglReady"
        class="scene-fallback"
        viewBox="0 0 460 560"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id="enamel"
            x1="145"
            y1="42"
            x2="331"
            y2="467"
            gradientUnits="userSpaceOnUse"
          >
            <stop stop-color="#fffef9" />
            <stop
              offset=".47"
              stop-color="#f2eee3"
            />
            <stop
              offset="1"
              stop-color="#dfd7c7"
            />
          </linearGradient>
          <linearGradient
            id="toothShade"
            x1="319"
            y1="122"
            x2="115"
            y2="460"
            gradientUnits="userSpaceOnUse"
          >
            <stop
              stop-color="#d4e8e5"
              stop-opacity=".3"
            />
            <stop
              offset="1"
              stop-color="#c9ba9f"
              stop-opacity=".48"
            />
          </linearGradient>
        </defs>
        <ellipse
          cx="235"
          cy="481"
          rx="132"
          ry="23"
          fill="#88aeb0"
          fill-opacity=".13"
        />
        <path
          d="M132 73c34-19 66 4 102 4s68-23 102-4c42 23 36 83 18 132-14 39-34 70-37 121-2 30-10 55-27 57-22 3-30-45-47-74-8-14-15-20-26-20s-18 6-26 20c-17 29-25 77-47 74-17-2-25-27-27-57-3-51-23-82-37-121-18-49-24-109 18-132Z"
          fill="url(#enamel)"
          stroke="#ddd5c6"
          stroke-width="2"
        />
        <path
          d="M118 147c32 18 72 26 116 26s84-8 116-26M121 191c33 17 72 25 113 25s80-8 113-25"
          stroke="url(#toothShade)"
          stroke-width="3"
          stroke-linecap="round"
        />
        <path
          d="M129 251c38 19 71 25 105 25s67-6 105-25"
          stroke="#d1c7b4"
          stroke-opacity=".5"
          stroke-width="2"
        />
        <ellipse
          cx="234"
          cy="249"
          rx="177"
          ry="205"
          stroke="#70c6ca"
          stroke-opacity=".52"
          stroke-width="1.4"
          transform="rotate(21 234 249)"
        />
        <ellipse
          cx="236"
          cy="246"
          rx="197"
          ry="222"
          stroke="#86bdbe"
          stroke-opacity=".33"
          stroke-width="1.2"
          transform="rotate(-27 236 246)"
        />
        <circle
          cx="353"
          cy="231"
          r="6"
          fill="#078c98"
        />
        <circle
          cx="353"
          cy="231"
          r="15"
          stroke="#078c98"
          stroke-opacity=".2"
        />
      </svg>

      <div
        class="scene-coordinate"
        aria-hidden="true"
      >
        <span>26</span><i />{{ isMobile ? 'DENTUM' : 'DENTUM · CLINICAL WORKSPACE' }}
      </div>

      <div
        v-if="storyStep > 0 && activeChapter"
        :key="storyStep"
        class="scene-card"
        aria-hidden="true"
      >
        <div class="scene-card__topline">
          <span class="scene-card__label"><i />{{ activeChapter.cardLabel }}</span>
          <span class="scene-card__mark">{{ activeChapter.cardMark }}</span>
        </div>
        <p class="scene-card__title">
          {{ activeChapter.cardTitle }}
        </p>
        <p class="scene-card__body">
          {{ activeChapter.cardBody }}
        </p>
        <div class="scene-card__meter">
          <i /><i /><i /><i />
        </div>
      </div>

      <div
        v-else
        class="scene-scroll-cue"
        aria-hidden="true"
      >
        <span />{{ scrollLabel }}
      </div>
      <div
        class="scene-coordinate scene-coordinate--bottom"
        aria-hidden="true"
      >
        {{ String(storyStep + 1).padStart(2, '0') }} <i /> 05
      </div>
      <div class="scene-credit">
        <a
          href="https://sketchfab.com/3d-models/maxillary-first-molar-e719a474ef7e4bd7abec508f85f1e984"
          target="_blank"
          rel="noopener noreferrer"
        >«Maxillary First Molar» · University of Dundee, School of Dentistry · Sketchfab</a>
        <span>·</span>
        <a
          href="https://creativecommons.org/licenses/by/4.0/"
          target="_blank"
          rel="noopener noreferrer"
        >CC BY 4.0</a>
        <span>· сглажена сетка, изменён материал</span>
      </div>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.dentum-story { position: relative; isolation: isolate; }
.scene-stage {
  position: sticky;
  z-index: 0;
  top: 0;
  height: 100svh;
  margin-bottom: -100svh;
  overflow: hidden;
  pointer-events: none;
  background: #f4f6f3;
}
.scene-stage__wash { position: absolute; inset: 0; background: radial-gradient(ellipse 44% 53% at 70% 48%, rgba(166, 222, 222, .32), rgba(218, 237, 233, .15) 45%, transparent 76%), linear-gradient(112deg, #f4f6f3 28%, #f3f6f3 65%, #f0f5f2); }
.scene-stage::after { position: absolute; top: 18%; right: 7.5%; width: min(36vw, 460px); aspect-ratio: 1; border: 1px solid rgba(41, 126, 136, .08); border-radius: 50%; content: ''; }
.scene-canvas { position: absolute; inset: 0; width: 100%; height: 100%; transform: translateX(16vw); }
.scene-fallback { position: absolute; top: 49%; left: 70%; width: min(42vw, 540px); max-height: 78svh; transform: translate(-50%, -50%); filter: drop-shadow(0 24px 28px rgba(93, 132, 131, .1)); }
.scene-coordinate { position: absolute; z-index: 2; top: 104px; right: clamp(28px, 8vw, 128px); display: flex; align-items: center; gap: 10px; color: #7c9296; font-size: 8px; font-weight: 650; letter-spacing: .13em; }
.scene-coordinate span { color: var(--landing-teal, #087f8c); font-size: 9px; }
.scene-coordinate i { display: block; width: 24px; height: 1px; background: #9ab8b7; }
.scene-coordinate--bottom { top: auto; right: auto; bottom: 42px; left: clamp(30px, 8vw, 128px); color: #9aa8a8; }
.scene-coordinate--bottom i { width: 32px; background: #bac6c4; }
.scene-credit { position: absolute; z-index: 4; right: clamp(24px, 7vw, 112px); bottom: 16px; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 5px; max-width: min(72vw, 620px); color: #7c9296; font-size: 8px; line-height: 1.4; letter-spacing: .015em; text-align: right; pointer-events: auto; }
.scene-credit a { color: inherit; text-decoration: underline; text-decoration-color: rgba(124, 146, 150, .45); text-underline-offset: 2px; }
.scene-card { position: absolute; z-index: 3; right: clamp(35px, 10vw, 160px); bottom: 17%; width: 250px; padding: 18px 19px 16px; border: 1px solid rgba(45, 107, 114, .17); border-radius: 6px; background: rgba(250, 252, 249, .84); box-shadow: 0 20px 54px rgba(48, 98, 101, .09); backdrop-filter: blur(16px); animation: card-in .42s cubic-bezier(.2,.8,.2,1) both; }
.scene-card__topline { display: flex; align-items: center; justify-content: space-between; }
.scene-card__label { display: flex; align-items: center; gap: 7px; color: #668185; font-size: 8px; font-weight: 700; letter-spacing: .12em; }
.scene-card__label i { width: 5px; height: 5px; border-radius: 50%; background: #1096a1; box-shadow: 0 0 0 3px rgba(16, 150, 161, .1); }
.scene-card__mark { display: grid; width: 27px; height: 27px; place-items: center; border: 1px solid rgba(8, 127, 140, .16); border-radius: 50%; color: #087f8c; font-size: 11px; font-weight: 650; }
.scene-card__title { margin: 15px 0 0; color: #1c373e; font-size: 16px; font-weight: 620; letter-spacing: -.035em; }
.scene-card__body { margin: 5px 0 0; color: #829294; font-size: 10px; }
.scene-card__meter { display: flex; gap: 4px; margin-top: 17px; }
.scene-card__meter i { display: block; width: 25px; height: 2px; border-radius: 2px; background: #a7d4d3; }
.scene-card__meter i:last-child { background: #e0ebe8; }
.scene-scroll-cue { position: absolute; z-index: 3; right: clamp(35px, 10vw, 160px); bottom: 17%; display: flex; align-items: center; gap: 10px; color: #789093; font-size: 9px; font-weight: 600; letter-spacing: .06em; }
.scene-scroll-cue span { display: block; width: 17px; height: 27px; border: 1px solid #7ea7a8; border-radius: 12px; }
.scene-scroll-cue span::after { display: block; width: 2px; height: 5px; margin: 5px auto; border-radius: 2px; background: var(--landing-teal, #087f8c); content: ''; animation: scroll-tick 1.3s ease-in-out infinite; }
@keyframes card-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes scroll-tick { 0%, 100% { opacity: .3; transform: translateY(0); } 55% { opacity: 1; transform: translateY(6px); } }

@media (max-width: 760px) {
  .scene-stage { height: 56svh; margin-bottom: -56svh; }
  .scene-stage__wash { background: radial-gradient(ellipse 83% 70% at 50% 43%, rgba(166, 222, 222, .37), rgba(218, 237, 233, .18) 57%, transparent 85%), linear-gradient(180deg, #f4f6f3 72%, rgba(244, 246, 243, .1)); }
  .scene-stage::after { top: 4%; right: 12%; width: 72vw; }
  .scene-fallback { top: 27%; left: 50%; width: min(70vw, 320px); max-height: 48svh; }
  .scene-coordinate { top: 78px; right: 20px; font-size: 7px; }
  .scene-coordinate--bottom { top: 47svh; right: 21px; bottom: auto; left: auto; font-size: 7px; }
  .scene-coordinate--bottom i { width: 20px; }
  .scene-coordinate--bottom { display: none; }
  .scene-credit { right: 18px; bottom: 10px; max-width: calc(100vw - 36px); gap: 3px; font-size: 7px; }
  .scene-canvas { transform: none; }
  .scene-card { right: 18px; bottom: auto; top: 41svh; width: min(215px, 61vw); padding: 12px 13px 11px; border-radius: 5px; }
  .scene-card__label { font-size: 7px; }
  .scene-card__mark { width: 23px; height: 23px; font-size: 9px; }
  .scene-card__title { margin-top: 9px; font-size: 13px; }
  .scene-card__body { font-size: 9px; }
  .scene-card__meter { margin-top: 10px; }
  .scene-card__meter i { width: 17px; }
  .scene-scroll-cue { top: 46svh; right: 20px; bottom: auto; max-width: 170px; gap: 7px; font-size: 8px; text-align: right; }
  .scene-scroll-cue span { flex: 0 0 auto; width: 13px; height: 21px; }
}

@media (prefers-reduced-motion: reduce) {
  .scene-scroll-cue span::after { animation: none; }
  .scene-card { animation: none; }
}
</style>
