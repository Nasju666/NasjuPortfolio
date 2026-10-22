// The 3D room. Loaded only when the visitor flips the switch.
//
// The room is a Blender scene with all lighting baked into its textures (see /blender), so the
// browser draws it unlit: no lights, no shadows, no shader work. That keeps it smooth on cheap phones.
// - The camera matches the Blender camera exactly and never moves from that spot; dragging turns it
//   a little (on phones, enough to pan across the room). Back faces were deleted at export, which
//   only works because the camera position never changes.
// - Frames are drawn only when something changes (drag, hover, resize, the clock ticking).
// - Low-end devices get a version with half-size textures.
import {
  Box3,
  CanvasTexture,
  Color,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  PerspectiveCamera,
  Raycaster,
  Scene,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  AdditiveBlending,
  AddEquation,
  CustomBlending,
  DstColorFactor,
  SrcColorFactor,
  Vector2,
  Vector3,
  WebGLRenderer,
  type Material,
  type Object3D,
  type Texture,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { sectionByObject } from '../../data/sections';
import { CAMERA_URL, MODEL_URL, MODEL_URL_LOW } from '../../data/room';
import { detectQuality, hasWebGL } from './quality';

export interface RoomHandle {
  pause(): void;
  resume(): void;
  highlight(object: string | null): void;
  /** Turn and zoom the camera onto an object (null = back to the normal view). */
  focus(object: string | null): void;
  dispose(): void;
}

interface Options {
  mount: HTMLElement;
  label: HTMLElement;
  onSelect(object: string): void;
  onHover(object: string | null): void;
  onProgress?(fraction: number): void;
  /** Pictures shown in the room (all optional). */
  media?: RoomMedia;
  /** Part of the screen not covered by an open panel, so close-ups can be framed inside it. */
  freeRect?(): { x: number; y: number; w: number; h: number };
}

export interface RoomMedia {
  /** Projects on the monitor (first four): name + screenshot. */
  monitor?: { title: string; img: string | null }[];
  /** App shown on the laptop screen. */
  laptop?: { title: string; img: string | null } | null;
  /** Photos pinned on the corkboard (up to seven). */
  board?: string[];
  /** Photo in the framed print on the shelf. */
  print?: string;
  /** Wide banner hanging on the wall above the shelf. */
  banner?: string;
}

interface BlenderCamera {
  position: [number, number, number];
  forward: [number, number, number];
  lens: number;
  sensorWidth: number;
  shiftX: number;
  shiftY: number;
  aspect: number;
}

interface Hotspot {
  name: string;
  group: Object3D;
  box: Box3;
  anchor: Vector3;
  materials: Array<{ m: Material & { color: Color }; base: Color }>;
  lift: number; // 0..1, animated
  target: number;
}

const HIGHLIGHT = 1.28; // brightness multiplier on hover
const LIFT = 0.025; // metres an object rises on hover

export async function createRoom(opts: Options): Promise<RoomHandle> {
  if (!hasWebGL()) throw new Error('no-webgl');
  const quality = detectQuality();
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Load camera + model ---------------------------------------------------
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const [cam, gltf] = await Promise.all([
    fetch(CAMERA_URL).then((r) => {
      if (!r.ok) throw new Error('camera');
      return r.json() as Promise<BlenderCamera>;
    }),
    loader.loadAsync(quality.tier === 'low' ? MODEL_URL_LOW : MODEL_URL, (e) => {
      if (e.lengthComputable) opts.onProgress?.(e.loaded / e.total);
    }),
  ]);

  // Renderer ----------------------------------------------------------------
  const renderer = new WebGLRenderer({ antialias: quality.antialias, powerPreference: 'low-power' });
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.setPixelRatio(quality.pixelRatio);
  renderer.setClearColor(0x120c0a, 1);
  const canvas = renderer.domElement;
  canvas.setAttribute('aria-hidden', 'true');
  opts.mount.prepend(canvas);
  const anisotropy = quality.tier === 'low' ? 1 : Math.min(4, renderer.capabilities.getMaxAnisotropy());

  // Render-on-demand state (declared early: the clock below asks for frames)
  let raf = 0;
  let paused = false;
  let hovered: Hotspot | null = null;
  let width = 0;
  let height = 0;

  // Scene: everything unlit, textures already contain the lighting ------------------
  const scene = new Scene();
  const room = gltf.scene;
  scene.add(room);
  const glowSources: Mesh[] = [];
  let clockMesh: Mesh | null = null;
  let monitorMesh: Mesh | null = null;
  let laptopMesh: Mesh | null = null;
  let printMesh: Mesh | null = null;
  let bannerMesh: Mesh | null = null;
  const photoMeshes: Mesh[] = [];
  room.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh) return;
    const toBasic = (m: Material) => {
      const src = m as MeshBasicMaterial;
      if (src.map) src.map.anisotropy = anisotropy;
      return new MeshBasicMaterial({ map: src.map ?? null, color: src.map ? 0xffffff : src.color });
    };
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(toBasic) : toBasic(mesh.material);
    if (mesh.name.startsWith('glow_')) glowSources.push(mesh);
    if (mesh.name === 'screen_clock') clockMesh = mesh;
    if (mesh.name === 'screen_monitor') monitorMesh = mesh;
    if (mesh.name === 'screen_laptop') laptopMesh = mesh;
    if (mesh.name === 'screen_print_photo') printMesh = mesh;
    if (mesh.name === 'screen_banner_photo') bannerMesh = mesh;
    if (mesh.name.startsWith('screen_photo_')) photoMeshes.push(mesh);
  });
  photoMeshes.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  const media = opts.media ?? {};
  room.updateMatrixWorld(true);

  // Soft halos around glowing parts (PC fans, LED strip). Cheap stand-in for a bloom pass.
  const halo = haloTexture();
  for (const g of glowSources) {
    const box = new Box3().setFromObject(g);
    const size = box.getSize(new Vector3());
    const center = box.getCenter(new Vector3());
    const color = ((g.material as MeshBasicMaterial).color ?? new Color(0x5aa0ff)).clone();
    const s = new Sprite(new SpriteMaterial({ map: halo, color, blending: AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.55 }));
    const long = Math.max(size.x, size.z);
    s.scale.set(Math.max(long * 1.25, 0.16), Math.max(size.y * 2.5, 0.16), 1);
    s.position.copy(g.parent ? g.parent.worldToLocal(center.clone()) : center);
    g.parent?.add(s);
  }

  // Live clock on the shelf: shows the visitor's local time.
  let clockTex: CanvasTexture | null = null;
  let clockTimer = 0;
  if (clockMesh) {
    const c = document.createElement('canvas');
    c.width = 512;
    c.height = 192;
    clockTex = new CanvasTexture(c);
    clockTex.colorSpace = SRGBColorSpace;
    clockTex.flipY = false; // glTF UV convention
    ((clockMesh as Mesh).material as MeshBasicMaterial).map = clockTex;
    const draw = () => {
      const g = c.getContext('2d')!;
      g.fillStyle = '#0d0f16';
      g.fillRect(0, 0, c.width, c.height);
      g.fillStyle = '#f4f6ff';
      g.font = `700 128px ${getComputedStyle(document.body).fontFamily}`;
      g.textAlign = 'center';
      g.textBaseline = 'middle';
      const t = new Date();
      g.fillText(`${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`, c.width / 2, c.height / 2 + 6);
      clockTex!.needsUpdate = true;
      requestRender();
    };
    draw();
    document.fonts?.ready.then(draw);
    const tick = () => {
      draw();
      clockTimer = window.setTimeout(tick, 60_000 - (Date.now() % 60_000) + 50);
    };
    clockTimer = window.setTimeout(tick, 60_000 - (Date.now() % 60_000) + 50);
  }

  // Pictures ---------------------------------------------------------------------------
  // Each picture is drawn into a canvas texture right away (so hover copies share it) and
  // redrawn once its image has loaded.
  const fontFamily = () => getComputedStyle(document.body).fontFamily;
  const images = new Map<string, Promise<HTMLImageElement | null>>();
  const loadImage = (url: string) => {
    if (!images.has(url)) {
      images.set(
        url,
        new Promise((resolve) => {
          const im = new Image();
          im.decoding = 'async';
          im.onload = () => resolve(im);
          im.onerror = () => resolve(null);
          im.src = url;
        }),
      );
    }
    return images.get(url)!;
  };
  /** Draw an image into a box: cropped to fill, or fitted whole on a matching background if the shapes differ a lot. */
  const drawPicture = (g: CanvasRenderingContext2D, im: HTMLImageElement, x: number, y: number, w: number, h: number) => {
    const ia = im.naturalWidth / im.naturalHeight;
    const ba = w / h;
    g.save();
    g.beginPath();
    g.rect(x, y, w, h);
    g.clip();
    if (Math.max(ia / ba, ba / ia) > 1.6) {
      // fit whole; fill the rest with the picture's own corner colour
      const probe = document.createElement('canvas');
      probe.width = probe.height = 1;
      const pg = probe.getContext('2d')!;
      pg.drawImage(im, 0, 0, 4, 4, 0, 0, 1, 1);
      const [r, gr, bl] = pg.getImageData(0, 0, 1, 1).data;
      g.fillStyle = `rgb(${r} ${gr} ${bl})`;
      g.fillRect(x, y, w, h);
      const s = Math.min(w / im.naturalWidth, h / im.naturalHeight);
      const dw = im.naturalWidth * s;
      const dh = im.naturalHeight * s;
      g.drawImage(im, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
    } else {
      const s = Math.max(w / im.naturalWidth, h / im.naturalHeight);
      const dw = im.naturalWidth * s;
      const dh = im.naturalHeight * s;
      g.drawImage(im, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh);
    }
    g.restore();
  };
  const canvasTexture = (w: number, h: number) => {
    const c = document.createElement('canvas');
    c.width = w;
    c.height = h;
    const tex = new CanvasTexture(c);
    tex.colorSpace = SRGBColorSpace;
    tex.flipY = false; // glTF UV convention
    tex.anisotropy = anisotropy;
    return { c, g: c.getContext('2d')!, tex };
  };
  const roundRect = (g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) => {
    g.beginPath();
    g.roundRect(x, y, w, h, r);
    g.fill();
  };
  const windowBar = (g: CanvasRenderingContext2D, w: number, h: number, title: string) => {
    g.fillStyle = '#1b2140';
    g.fillRect(0, 0, w, h);
    ['#e0605e', '#f4b740', '#5ec27a'].forEach((col, i) => {
      g.fillStyle = col;
      g.beginPath();
      g.arc(h * 0.55 + i * h * 0.6, h / 2, h * 0.16, 0, Math.PI * 2);
      g.fill();
    });
    g.fillStyle = '#9aa3c7';
    g.font = `400 ${Math.round(h * 0.45)}px ${fontFamily()}`;
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText(title, w / 2, h / 2 + 1);
    g.textBaseline = 'alphabetic';
  };

  // Monitor: the first four projects with their screenshots, so the room matches the content files.
  const monitorItems = (media.monitor ?? []).slice(0, 4);
  if (monitorMesh && monitorItems.length) {
    const { c, g, tex } = canvasTexture(1344, 576);
    ((monitorMesh as Mesh).material as MeshBasicMaterial).map = tex;
    const pics: (HTMLImageElement | null)[] = monitorItems.map(() => null);
    const draw = () => {
      g.fillStyle = '#12162a';
      g.fillRect(0, 0, c.width, c.height);
      windowBar(g, c.width, 44, 'nasju / projects');
      g.textAlign = 'left';
      g.fillStyle = '#ffffff';
      g.font = `700 44px ${fontFamily()}`;
      g.fillText('Projects', 60, 128);
      const colors = ['#3b6cf5', '#21b07a', '#f4b740', '#9b6cf5'];
      const n = monitorItems.length;
      const cw = 280;
      const gap = 34;
      const x0 = (c.width - (cw * n + gap * (n - 1))) / 2;
      monitorItems.forEach((item, i) => {
        const x = x0 + i * (cw + gap);
        const y = 176;
        g.fillStyle = '#1d2342';
        roundRect(g, x, y, cw, 330, 22);
        g.fillStyle = colors[i % colors.length];
        roundRect(g, x + 14, y + 14, cw - 28, 200, 14);
        const im = pics[i];
        if (im) {
          g.save();
          g.beginPath();
          g.roundRect(x + 14, y + 14, cw - 28, 200, 14);
          g.clip();
          drawPicture(g, im, x + 14, y + 14, cw - 28, 200);
          g.restore();
        }
        g.fillStyle = '#ffffff';
        let size = 30;
        g.font = `700 ${size}px ${fontFamily()}`;
        while (g.measureText(item.title).width > cw - 44 && size > 18) g.font = `700 ${--size}px ${fontFamily()}`;
        let label = item.title;
        while (g.measureText(label).width > cw - 44 && label.length > 4) label = label.slice(0, -2) + '…';
        g.fillText(label, x + 22, y + 262);
        g.fillStyle = '#39406a';
        roundRect(g, x + 22, y + 284, cw - 92, 12, 6);
        roundRect(g, x + 22, y + 306, cw - 142, 12, 6);
      });
      tex.needsUpdate = true;
      requestRender();
    };
    draw();
    document.fonts?.ready.then(draw);
    monitorItems.forEach((item, i) => {
      if (item.img)
        loadImage(item.img).then((im) => {
          pics[i] = im;
          if (im) draw();
        });
    });
  }

  // Laptop: the client app, in a browser-like window.
  const laptopItem = media.laptop;
  if (laptopMesh && laptopItem?.img) {
    const { c, g, tex } = canvasTexture(960, 608);
    ((laptopMesh as Mesh).material as MeshBasicMaterial).map = tex;
    let pic: HTMLImageElement | null = null;
    const draw = () => {
      g.fillStyle = '#f2f3f7';
      g.fillRect(0, 0, c.width, c.height);
      windowBar(g, c.width, 48, laptopItem.title);
      if (pic) drawPicture(g, pic, 0, 48, c.width, c.height - 48);
      tex.needsUpdate = true;
      requestRender();
    };
    draw();
    document.fonts?.ready.then(draw);
    loadImage(laptopItem.img).then((im) => {
      pic = im;
      if (im) draw();
    });
  }

  // Photos (corkboard, wall banner, framed print). The paper under each one is baked with the
  // room's light, so the photo is blended on top of it ("multiply x2"): it picks up the same
  // shading and pin shadows, while the picture itself stays sharp.
  const PHOTO_GAIN = 0.33; // tuned so a photo on the brightest paper shows at about its true colours
  const photoLayer = (mesh: Mesh, url: string | undefined, w: number, h: number) => {
    const { g, tex } = canvasTexture(w, h);
    g.fillStyle = '#808080'; // neutral until loaded: leaves the paper as it is
    g.fillRect(0, 0, w, h);
    tex.needsUpdate = true;
    mesh.material = new MeshBasicMaterial({
      map: tex,
      color: new Color().setScalar(PHOTO_GAIN),
      transparent: true,
      depthWrite: false,
      blending: CustomBlending,
      blendEquation: AddEquation,
      blendSrc: DstColorFactor,
      blendDst: SrcColorFactor,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    });
    mesh.renderOrder = 2;
    if (!url) {
      mesh.visible = false;
      return;
    }
    loadImage(url).then((im) => {
      if (!im) return (mesh.visible = false);
      drawPicture(g, im, 0, 0, w, h);
      tex.needsUpdate = true;
      requestRender();
    });
  };
  photoMeshes.forEach((m, i) => photoLayer(m, media.board?.[i], 640, 480));
  if (printMesh) photoLayer(printMesh, media.print, 500, 600);
  if (bannerMesh) photoLayer(bannerMesh, media.banner, 1280, 474);

  // Hotspots ---------------------------------------------------------------------------
  const hotspots: Hotspot[] = [];
  room.traverse((o) => {
    if (!o.name.startsWith('hit_')) return;
    const box = new Box3().setFromObject(o);
    const center = box.getCenter(new Vector3());
    // Own material copies so highlighting one object never lights up another.
    const own = new Map<Material, Material>();
    const materials: Hotspot['materials'] = [];
    o.traverse((c) => {
      const mesh = c as Mesh;
      if (!mesh.isMesh) return;
      const swap = (m: Material) => {
        if (!own.has(m)) {
          const clone = m.clone() as MeshBasicMaterial;
          own.set(m, clone);
          materials.push({ m: clone, base: clone.color.clone() });
        }
        return own.get(m)!;
      };
      mesh.material = Array.isArray(mesh.material) ? mesh.material.map(swap) : swap(mesh.material);
    });
    hotspots.push({ name: o.name.slice(4), group: o, box, anchor: new Vector3(center.x, box.max.y, center.z), materials, lift: 0, target: 0 });
  });
  const byName = new Map(hotspots.map((h) => [h.name, h]));
  const hotspotOf = (o: Object3D | null): Hotspot | null => {
    for (let p = o; p; p = p.parent) if (p.name.startsWith('hit_')) return byName.get(p.name.slice(4)) ?? null;
    return null;
  };
  const pickables: Object3D[] = [];
  room.traverse((o) => {
    if ((o as Mesh).isMesh) pickables.push(o);
  });

  // Camera: same spot, lens and framing as the Blender camera ------------------------------------
  const camera = new PerspectiveCamera(40, 1, 0.05, 40);
  camera.position.fromArray(cam.position);
  const fwd0 = new Vector3().fromArray(cam.forward).normalize();
  const up = new Vector3(0, 1, 0);
  const halfH = Math.atan(cam.sensorWidth / 2 / cam.lens); // Blender's horizontal half-angle
  const halfV0 = Math.atan(Math.tan(halfH) / cam.aspect); // ...and vertical, at the render's aspect

  // Look-around state (radians, relative to the Blender direction), set by dragging.
  let yaw = 0;
  let pitch = 0;
  let yawTarget = 0;
  let pitchTarget = 0;
  let yawRange = 0.05;
  const pitchRange = 0.035;
  let halfVNow = halfV0;
  let halfHNow = halfH;
  let baseOffX = 0;
  let baseOffY = 0;

  // What the camera shows: direction, zoom (vertical half-angle) and where on screen the
  // centre of view sits (projection offset in pixels). Blends between the look-around view and
  // a close-up of one object. The camera never changes position, only where it points and zooms.
  interface View {
    yaw: number;
    pitch: number;
    halfV: number;
    offX: number;
    offY: number;
  }
  const view: View = { yaw: 0, pitch: 0, halfV: halfV0, offX: 0, offY: 0 };
  let focused: Hotspot | null = null;
  let tween: { from: View; start: number; dur: number } | null = null;

  // Angle from the base view direction to a point, around the vertical axis (left = positive).
  const yawTo = (p: Vector3) => {
    const d = p.clone().sub(camera.position);
    d.y = 0;
    const f = fwd0.clone();
    f.y = 0;
    return Math.atan2(f.clone().cross(d).y, f.dot(d));
  };
  const pitchTo = (p: Vector3) => {
    const d = p.clone().sub(camera.position);
    return Math.atan2(d.y, Math.hypot(d.x, d.z));
  };

  function baseView(): View {
    return { yaw, pitch, halfV: halfVNow, offX: baseOffX, offY: baseOffY };
  }

  // Close-up framing: point straight at the object, zoom so it fills most of the screen area
  // the panel leaves free, and slide the picture so the object sits in the middle of that area.
  function focusView(h: Hotspot): View {
    const c = h.box.getCenter(new Vector3());
    const r = h.box.getSize(new Vector3()).length() / 2;
    const dist = c.distanceTo(camera.position);
    const free = opts.freeRect?.() ?? { x: 0, y: 0, w: width, h: height };
    const fw = Math.max(80, Math.min(free.w, width));
    const fh = Math.max(80, Math.min(free.h, height));
    const tr = r / Math.sqrt(Math.max(1e-6, dist * dist - r * r)); // angular radius, as a tangent
    const fill = 0.7; // object diameter as a share of the free area's shorter side
    const halfV = MathUtils.clamp(Math.atan((tr * height) / (fill * Math.min(fw, fh))), MathUtils.degToRad(4), halfVNow);
    return {
      yaw: yawTo(c),
      pitch: pitchTo(c),
      halfV,
      offX: width / 2 - (free.x + fw / 2),
      offY: height / 2 - (free.y + fh / 2),
    };
  }

  function applyView(v: View) {
    const f = fwd0.clone().applyAxisAngle(up, v.yaw);
    const right = f.clone().cross(up).normalize();
    f.applyAxisAngle(right, v.pitch);
    camera.up.copy(up);
    camera.lookAt(camera.position.clone().add(f));
    camera.fov = MathUtils.radToDeg(v.halfV * 2);
    camera.aspect = width / height;
    camera.setViewOffset(width, height, v.offX, v.offY, width, height);
    camera.updateProjectionMatrix();
  }

  const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  function focusOn(name: string | null) {
    const next = name ? byName.get(name) ?? null : null;
    if (next === focused) return;
    if (focused) focused.target = 0;
    focused = next;
    if (next) {
      setHover(null);
      next.target = 1; // keep the chosen object lifted while it's open
    }
    tween = reduced ? null : { from: { ...view }, start: performance.now(), dur: next ? 850 : 700 };
    requestRender();
  }

  // Sizing --------------------------------------------------------------------------------------
  function resize() {
    const w = opts.mount.clientWidth;
    const h = opts.mount.clientHeight;
    if (!w || !h || (w === width && h === height)) return;
    width = w;
    height = h;
    renderer.setSize(w, h, false);
    const aspect = w / h;
    if (aspect >= cam.aspect) {
      halfVNow = halfV0; // wider than the render: same height, a little more of the sides
    } else if (aspect >= 1) {
      halfVNow = Math.atan(Math.tan(halfH) / aspect); // keep the full width of the render
    } else {
      halfVNow = Math.atan(Math.tan(halfV0) * 1.3); // phones: a bit taller view, pan sideways to see the rest
    }
    halfHNow = Math.atan(Math.tan(halfVNow) * aspect);
    // Blender's lens shift, as a projection offset (keeps vertical lines straight).
    const plane = cam.sensorWidth / cam.lens; // shift is measured in sensor widths
    baseOffX = (cam.shiftX * plane) / (2 * Math.tan(halfHNow)) * w;
    baseOffY = (-cam.shiftY * plane) / (2 * Math.tan(halfVNow)) * h;
    // Phones: lift the desk above the button dock (there's spare wall at the top anyway).
    if (aspect < 1) baseOffY += h * 0.12;

    const wasPortrait = yawRange > 0.05;
    yawRange = Math.max(0.05, halfH - halfHNow);
    if (yawRange > 0.05 && !wasPortrait) {
      // Phones start looking at the monitor.
      const mon = byName.get('monitor');
      if (mon) yaw = yawTarget = MathUtils.clamp(yawTo(mon.box.getCenter(new Vector3())), -yawRange, yawRange);
    }
    yawTarget = MathUtils.clamp(yawTarget, -yawRange, yawRange);
    yaw = MathUtils.clamp(yaw, -yawRange, yawRange);
    requestRender();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(opts.mount);

  // Render loop (on demand) ----------------------------------------------------------------------

  function step(): boolean {
    let moving = false;
    // Look-around damping (only while not focused on an object)
    if (!focused) {
      const k = reduced ? 1 : 0.16;
      if (Math.abs(yawTarget - yaw) > 1e-4 || Math.abs(pitchTarget - pitch) > 1e-4) {
        yaw += (yawTarget - yaw) * k;
        pitch += (pitchTarget - pitch) * k;
        moving = true;
      }
    }
    const goal = focused ? focusView(focused) : baseView();
    if (tween) {
      const t = Math.min(1, (performance.now() - tween.start) / tween.dur);
      const e = ease(t);
      for (const k of Object.keys(goal) as Array<keyof View>) view[k] = tween.from[k] + (goal[k] - tween.from[k]) * e;
      if (t >= 1) tween = null;
      else moving = true;
    } else {
      Object.assign(view, goal);
    }
    applyView(view);

    for (const h of hotspots) {
      const d = h.target - h.lift;
      if (Math.abs(d) < 0.002) {
        if (h.lift !== h.target) {
          h.lift = h.target;
          applyLift(h);
        }
        continue;
      }
      h.lift += reduced ? d : d * 0.22;
      applyLift(h);
      moving = true;
    }
    return moving;
  }
  function applyLift(h: Hotspot) {
    h.group.position.y = h.lift * LIFT;
    const f = 1 + (HIGHLIGHT - 1) * h.lift;
    for (const { m, base } of h.materials) m.color.copy(base).multiplyScalar(f);
  }

  function frame() {
    raf = 0;
    if (paused) return;
    const moving = step();
    renderer.render(scene, camera);
    placeLabel();
    if (moving) requestRender();
  }
  function requestRender() {
    if (!raf && !paused) raf = requestAnimationFrame(frame);
  }

  // Hover label --------------------------------------------------------------------------------
  const titleOf = (name: string) => sectionByObject(name)?.title ?? name;
  const tmp = new Vector3();
  opts.label.style.left = '0';
  opts.label.style.top = '0';
  function placeLabel() {
    if (!hovered) {
      opts.label.hidden = true;
      return;
    }
    tmp.copy(hovered.anchor);
    tmp.y += hovered.lift * LIFT;
    tmp.project(camera);
    const x = (tmp.x * 0.5 + 0.5) * width;
    const y = (-tmp.y * 0.5 + 0.5) * height;
    opts.label.style.transform = `translate(${x}px, ${y}px) translate(-50%, calc(-100% - 10px))`;
    opts.label.hidden = false;
  }
  function setHover(h: Hotspot | null) {
    if (h === hovered) return;
    if (hovered) hovered.target = 0;
    hovered = h;
    if (h) {
      h.target = 1;
      opts.label.textContent = titleOf(h.name);
    }
    canvas.style.cursor = h ? 'pointer' : '';
    opts.onHover(h?.name ?? null);
    requestRender();
  }

  // Picking: exact hit first (so things in front block things behind), then a forgiving
  // fallback for small objects on touch screens.
  const ray = new Raycaster();
  const ndc = new Vector2();
  const padded = new Box3();
  const hitPoint = new Vector3();
  function pick(clientX: number, clientY: number, forgiving: boolean): Hotspot | null {
    const r = canvas.getBoundingClientRect();
    ndc.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const first = ray.intersectObjects(pickables, false)[0];
    const exact = first ? hotspotOf(first.object) : null;
    if (exact || !forgiving) return exact;
    let best: Hotspot | null = null;
    let bestVol = Infinity;
    for (const h of hotspots) {
      padded.copy(h.box).expandByScalar(0.04);
      if (!ray.ray.intersectBox(padded, hitPoint)) continue;
      if (first && hitPoint.distanceTo(ray.ray.origin) > first.distance + 0.05) continue; // hidden behind something
      const s = h.box.getSize(tmp);
      const vol = s.x * s.y * s.z;
      if (vol < bestVol) {
        bestVol = vol;
        best = h;
      }
    }
    return best;
  }

  // Input: drag to look around, tap/click to open ------------------------------------------------
  let down: { x: number; y: number; t: number; yaw: number; pitch: number; id: number } | null = null;
  let dragged = false;
  let moveQueued = false;
  let lastMove: PointerEvent | null = null;
  const onDown = (e: PointerEvent) => {
    down = { x: e.clientX, y: e.clientY, t: performance.now(), yaw: yawTarget, pitch: pitchTarget, id: e.pointerId };
    dragged = false;
  };
  const onMove = (e: PointerEvent) => {
    if (down && e.pointerId === down.id) {
      const dx = e.clientX - down.x;
      const dy = e.clientY - down.y;
      if (!dragged && Math.hypot(dx, dy) > 6) {
        dragged = true;
        try {
          canvas.setPointerCapture(e.pointerId);
        } catch {
          /* pointer already gone */
        }
        setHover(null);
      }
      if (dragged) {
        // Content follows the finger: drag right to look left.
        yawTarget = MathUtils.clamp(down.yaw + (dx / width) * halfHNow * 2, -yawRange, yawRange);
        pitchTarget = MathUtils.clamp(down.pitch + (dy / height) * halfVNow * 2, -pitchRange, pitchRange);
        requestRender();
      }
      return;
    }
    if (e.pointerType !== 'mouse') return;
    lastMove = e;
    if (moveQueued) return;
    moveQueued = true;
    requestAnimationFrame(() => {
      moveQueued = false;
      if (lastMove && !paused && !down && !focused) setHover(pick(lastMove.clientX, lastMove.clientY, false));
    });
  };
  const onUp = (e: PointerEvent) => {
    if (!down || e.pointerId !== down.id) return;
    const quick = performance.now() - down.t < 600;
    const wasDrag = dragged;
    down = null;
    dragged = false;
    if (wasDrag || !quick) return;
    const h = pick(e.clientX, e.clientY, e.pointerType !== 'mouse');
    if (!h) {
      if (e.pointerType !== 'mouse') setHover(null);
      return;
    }
    setHover(h);
    // On touch, let the lift and label show for a moment before the panel covers them.
    setTimeout(() => opts.onSelect(h.name), e.pointerType === 'mouse' ? 0 : 140);
  };
  const onCancel = () => {
    down = null;
    dragged = false;
  };
  const onLeave = () => {
    if (!down) setHover(null);
  };
  canvas.addEventListener('pointerdown', onDown);
  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('pointercancel', onCancel);
  canvas.addEventListener('pointerleave', onLeave);

  resize();

  // First visit: each clickable object glows once, in turn, so people see what they can open.
  if (!reduced) {
    hotspots.forEach((h, i) => {
      setTimeout(() => {
        if (hovered) return;
        h.target = 1;
        requestRender();
        setTimeout(() => {
          if (hovered !== h) {
            h.target = 0;
            requestRender();
          }
        }, 380);
      }, 600 + i * 150);
    });
  }

  return {
    pause() {
      paused = true;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    },
    resume() {
      paused = false;
      width = 0; // force a size check; the window may have changed while hidden
      resize();
      requestRender();
    },
    highlight(name) {
      if (focused) return;
      setHover(name ? byName.get(name) ?? null : null);
    },
    focus: focusOn,
    dispose() {
      ro.disconnect();
      clearTimeout(clockTimer);
      canvas.remove();
      scene.traverse((o) => {
        const m = o as Mesh;
        if (m.isMesh) {
          m.geometry.dispose();
          (Array.isArray(m.material) ? m.material : [m.material]).forEach((mat) => mat.dispose());
        }
      });
      halo.dispose();
      renderer.dispose();
    },
  };
}

function haloTexture(): Texture {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d')!;
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, 'rgba(255,255,255,0.9)');
  grd.addColorStop(0.35, 'rgba(255,255,255,0.35)');
  grd.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 64, 64);
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  return t;
}
