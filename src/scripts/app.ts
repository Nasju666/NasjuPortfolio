// Page behaviour shared by both modes: the detail panel, the room switch, and section highlighting.
// Kept small on purpose; the 3D room code is a separate chunk loaded on demand.
import { SECTIONS, sectionByObject, type SectionId } from '../data/sections';
import type { RoomHandle } from './room/index';

const $ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document) => root.querySelector(sel) as T;
const $$ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document) =>
  Array.from(root.querySelectorAll(sel)) as T[];

const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const store = {
  get(k: string) {
    try {
      return localStorage.getItem(k);
    } catch {
      return null;
    }
  },
  set(k: string, v: string) {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* private mode etc. */
    }
  },
};

/* ------------------------------------------------------------------
   Detail panel (one <dialog>, a small back stack)
------------------------------------------------------------------- */
interface View {
  title: string;
  render: () => Node;
}
const sheet = $<HTMLDialogElement>('#sheet');
const sheetBody = $('#sheet-body');
const sheetTitle = $('#sheet-title');
const backBtn = $<HTMLButtonElement>('#sheet-back');
let stack: View[] = [];
const sheetListeners: Array<(open: boolean) => void> = [];

function showTop() {
  const view = stack[stack.length - 1];
  if (!view) return;
  sheetTitle.textContent = view.title;
  sheetBody.replaceChildren(view.render());
  sheetBody.scrollTop = 0;
  backBtn.hidden = stack.length < 2;
}

function openView(view: View, push: boolean) {
  stack = push && sheet.open ? [...stack, view] : [view];
  showTop();
  if (!sheet.open) {
    sheet.showModal();
    sheetListeners.forEach((fn) => fn(true));
  }
  // Move focus into the content, not the close button, so screen readers start at the heading.
  sheetTitle.setAttribute('tabindex', '-1');
  sheetTitle.focus({ preventScroll: true });
}

function openDetail(key: string) {
  const tpl = document.getElementById(`d-${key}`) as HTMLTemplateElement | null;
  if (!tpl) return;
  openView({ title: tpl.dataset.title ?? '', render: () => tpl.content.cloneNode(true) }, true);
}

function openSection(id: SectionId) {
  const body = $(`[data-body="${id}"]`);
  const def = SECTIONS.find((s) => s.id === id);
  if (!body || !def) return;
  openView({ title: def.title, render: () => body.cloneNode(true) }, false);
}

function closeSheet() {
  if (sheet.open) sheet.close();
}

sheet.addEventListener('close', () => {
  stack = [];
  sheetBody.replaceChildren();
  sheetListeners.forEach((fn) => fn(false));
});
backBtn.addEventListener('click', () => {
  stack.pop();
  showTop();
});
$('#sheet-close').addEventListener('click', closeSheet);
// Click on the dimmed backdrop closes the panel.
sheet.addEventListener('click', (e) => {
  if (e.target === sheet) closeSheet();
});

// Swipe the bottom sheet down to close it (phones).
{
  let startY = 0;
  let dy = 0;
  let dragging = false;
  const handle = (e: TouchEvent) => (e.target as Element).closest('.sheet-grip, .sheet-head');
  sheet.addEventListener(
    'touchstart',
    (e) => {
      if (!handle(e) || innerWidth > 640) return;
      dragging = true;
      startY = e.touches[0].clientY;
      dy = 0;
    },
    { passive: true },
  );
  sheet.addEventListener(
    'touchmove',
    (e) => {
      if (!dragging) return;
      dy = Math.max(0, e.touches[0].clientY - startY);
      sheet.style.transform = `translateY(${dy}px)`;
    },
    { passive: true },
  );
  sheet.addEventListener('touchend', () => {
    if (!dragging) return;
    dragging = false;
    sheet.style.transform = '';
    if (dy > 90) closeSheet();
  });
}

// Any [data-open] row, on the page or inside the panel, opens its detail.
document.addEventListener('click', (e) => {
  const row = (e.target as Element).closest<HTMLElement>('[data-open]');
  if (row?.dataset.open) openDetail(row.dataset.open);
});

/* ------------------------------------------------------------------
   Galleries (in the detail panel) and the full-screen picture viewer
------------------------------------------------------------------- */
interface Pic {
  src: string;
  alt: string;
  w: number;
  h: number;
}
const picsOf = (g: HTMLElement): Pic[] =>
  $$<HTMLElement>('[data-pic]', g).map((b) => ({ src: b.dataset.src!, alt: b.dataset.alt ?? '', w: +b.dataset.w!, h: +b.dataset.h! }));

function showInGallery(g: HTMLElement, i: number) {
  const pics = picsOf(g);
  if (!pics.length) return;
  i = (i + pics.length) % pics.length;
  g.dataset.index = String(i);
  const img = $<HTMLImageElement>('[data-main] img', g);
  img.src = pics[i].src;
  img.alt = pics[i].alt;
  img.width = pics[i].w;
  img.height = pics[i].h;
  const count = $('.gallery-count', g);
  if (count) count.textContent = `${i + 1} / ${pics.length}`;
  $$<HTMLElement>('.gallery-thumbs [data-pic]', g).forEach((b, k) => {
    if (k === i) {
      b.setAttribute('aria-current', 'true');
      b.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    } else b.removeAttribute('aria-current');
  });
}

const lightbox = $<HTMLDialogElement>('#lightbox');
const lbImg = $<HTMLImageElement>('#lb-img');
let lbPics: Pic[] = [];
let lbIndex = 0;
let lbGallery: HTMLElement | null = null;

function showLightbox(i: number) {
  lbIndex = (i + lbPics.length) % lbPics.length;
  const p = lbPics[lbIndex];
  lbImg.src = p.src;
  lbImg.alt = p.alt;
  $('#lb-caption').textContent = p.alt;
  $('#lb-count').textContent = lbPics.length > 1 ? `${lbIndex + 1} / ${lbPics.length}` : '';
  $$<HTMLButtonElement>('.lb-nav').forEach((b) => (b.hidden = lbPics.length < 2));
  if (lbGallery) showInGallery(lbGallery, lbIndex); // keep the panel in step
}
function openLightbox(g: HTMLElement) {
  lbPics = picsOf(g);
  if (!lbPics.length) return;
  lbGallery = g;
  showLightbox(+(g.dataset.index ?? 0));
  lightbox.showModal();
}

document.addEventListener('click', (e) => {
  const t = e.target as Element;
  const g = t.closest<HTMLElement>('[data-gallery]');
  if (!g) return;
  const step = t.closest<HTMLElement>('[data-gallery-step]');
  if (step) return showInGallery(g, +(g.dataset.index ?? 0) + +step.dataset.galleryStep!);
  const thumb = t.closest<HTMLElement>('.gallery-thumbs [data-pic]');
  if (thumb) return showInGallery(g, $$('.gallery-thumbs [data-pic]', g).indexOf(thumb));
  if (t.closest('[data-main]')) openLightbox(g);
});

$('#lb-close').addEventListener('click', () => lightbox.close());
$('#lb-prev').addEventListener('click', () => showLightbox(lbIndex - 1));
$('#lb-next').addEventListener('click', () => showLightbox(lbIndex + 1));
// Click the dark area around the picture to close.
lightbox.addEventListener('click', (e) => {
  if (e.target === lightbox || (e.target as Element).classList.contains('lb-figure')) lightbox.close();
});
lightbox.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowLeft') showLightbox(lbIndex - 1);
  if (e.key === 'ArrowRight') showLightbox(lbIndex + 1);
});
// Swipe left/right on touch screens.
{
  let x0 = 0;
  let y0 = 0;
  lightbox.addEventListener('pointerdown', (e) => {
    x0 = e.clientX;
    y0 = e.clientY;
  });
  lightbox.addEventListener('pointerup', (e) => {
    const dx = e.clientX - x0;
    if (e.pointerType !== 'mouse' && Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(e.clientY - y0) && lbPics.length > 1) {
      showLightbox(lbIndex + (dx < 0 ? 1 : -1));
    }
  });
}

/* ------------------------------------------------------------------
   Highlight the current section in the side contents
------------------------------------------------------------------- */
{
  // The current section is the last one whose top has scrolled past a line near the top of the
  // screen; at the very bottom of the page it's always the last section (short sections like
  // Contact can never reach that line otherwise). Clicking a menu link highlights it right away.
  const links = new Map($$<HTMLAnchorElement>('.toc a').map((a) => [a.hash.slice(1), a]));
  const sections = SECTIONS.map((s) => document.getElementById(s.id)).filter((el): el is HTMLElement => !!el);
  let current = '';
  let lockUntil = 0;
  const setCurrent = (id: string) => {
    if (id === current) return;
    current = id;
    links.forEach((a, key) => (key === id ? a.setAttribute('aria-current', 'true') : a.removeAttribute('aria-current')));
  };
  const update = () => {
    if (performance.now() < lockUntil) return;
    const line = Math.min(innerHeight * 0.3, 220);
    let id = sections[0]?.id ?? '';
    for (const el of sections) if (el.getBoundingClientRect().top <= line) id = el.id;
    if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) id = sections[sections.length - 1].id;
    setCurrent(id);
  };
  let queued = false;
  addEventListener(
    'scroll',
    () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        update();
      });
    },
    { passive: true },
  );
  addEventListener('resize', update);
  links.forEach((a, id) =>
    a.addEventListener('click', () => {
      setCurrent(id);
      lockUntil = performance.now() + 900; // let the smooth scroll finish before tracking again
      setTimeout(update, 950);
    }),
  );
  update();
}

/* ------------------------------------------------------------------
   Room mode
------------------------------------------------------------------- */
const root = document.documentElement;
const stage = $('#stage');
const status = $('#stage-status');
const shell = $('.shell');
const switches = $$<HTMLButtonElement>('.js-room-switch');
const dockButtons = $$<HTMLButtonElement>('.dock button');
let room: RoomHandle | null = null;
let booting: Promise<RoomHandle | null> | null = null;
let inRoom = false;
let returnFocus: HTMLElement | null = null;

function syncSwitches() {
  for (const b of switches) {
    b.setAttribute('aria-pressed', String(inRoom));
    const label = $('.js-switch-label', b);
    if (label) label.textContent = inRoom ? 'Back to the page' : 'Enter the room';
    const hint = $('.js-switch-hint', b);
    if (hint) hint.textContent = inRoom ? 'Simple version' : 'See this portfolio in 3D';
  }
}

function showStatus(html: string | null) {
  status.hidden = html === null;
  status.innerHTML = html ?? '';
}

async function bootRoom(): Promise<RoomHandle | null> {
  showStatus('<div><div class="spinner"></div><p>Setting up the room… <span class="js-pct"></span></p></div>');
  try {
    const mod = await import('./room/index');
    const handle = await mod.createRoom({
      mount: stage,
      label: $('#hotspot-label'),
      onSelect: (object) => openFromRoom(object),
      media: JSON.parse($('#room-media')?.textContent || '{}'),
      freeRect: () => {
        // The stage bar (name + switch) sits at the top; keep close-ups below it.
        const top = 64;
        const w = innerWidth;
        const h = innerHeight;
        if (!sheet.open) return { x: 0, y: top, w, h: h - top };
        if (w > 640) {
          const left = w - sheet.offsetWidth; // side panel on the right
          return left > 280 ? { x: 0, y: top, w: left, h: h - top } : { x: 0, y: top, w, h: h - top };
        }
        return { x: 0, y: top, w, h: Math.max(120, h - sheet.offsetHeight - top) }; // bottom sheet
      },
      onHover: (object) => {
        dockButtons.forEach((b) => b.classList.toggle('is-hot', b.dataset.object === object));
      },
      onProgress: (f) => {
        const pct = $('.js-pct', status);
        if (pct) pct.textContent = `${Math.round(f * 100)}%`;
      },
    });
    showStatus(null);
    return handle;
  } catch (err) {
    console.error(err);
    const reason =
      (err as Error)?.message === 'no-webgl'
        ? "This browser or device can't show the 3D room."
        : "The room couldn't load this time.";
    showStatus(`<div><p>${reason}</p><button type="button" class="js-leave">Back to the page</button></div>`);
    $('.js-leave', status)?.addEventListener('click', () => leaveRoom());
    booting = null;
    return null;
  }
}

async function enterRoom(origin?: HTMLElement, animate = true) {
  if (inRoom) return;
  inRoom = true;
  returnFocus = origin ?? null;
  store.set('portfolio-mode', 'room');
  syncSwitches();

  if (origin) {
    const r = origin.getBoundingClientRect();
    stage.style.setProperty('--ox', `${r.left + r.width / 2}px`);
    stage.style.setProperty('--oy', `${r.top + r.height / 2}px`);
  }
  stage.classList.remove('leaving');
  stage.hidden = false;
  if (animate && !reducedMotion()) {
    stage.classList.add('revealing');
    stage.addEventListener('animationend', () => stage.classList.remove('revealing'), { once: true });
  }
  root.classList.add('in-room');
  shell.inert = true;
  $<HTMLButtonElement>('.stage .js-room-switch')?.focus({ preventScroll: true });

  if (!room) {
    booting ??= bootRoom();
    room = await booting;
  }
  if (inRoom) room?.resume();
}

function leaveRoom() {
  if (!inRoom) return;
  inRoom = false;
  store.set('portfolio-mode', 'page');
  syncSwitches();
  closeSheet();
  room?.pause();

  const finish = () => {
    stage.hidden = true;
    stage.classList.remove('leaving');
    root.classList.remove('in-room');
    shell.inert = false;
    (returnFocus && document.contains(returnFocus) && returnFocus.offsetParent ? returnFocus : switches.find((s) => s.offsetParent && !stage.contains(s)))?.focus({
      preventScroll: true,
    });
  };
  if (reducedMotion()) return finish();
  stage.classList.remove('revealing');
  stage.classList.add('leaving');
  stage.addEventListener('animationend', finish, { once: true });
}

for (const b of switches) {
  b.addEventListener('click', () => (inRoom ? leaveRoom() : enterRoom(b)));
}

// Open a section from the room, and turn the camera to the object it belongs to.
function openFromRoom(object: string) {
  const s = sectionByObject(object);
  if (!s) return;
  openSection(s.id);
  room?.focus(object);
}

// Links like the "New game" pill: scroll to their section on the page and flash its spotlight;
// inside the 3D room (where there's no page to scroll) open that section's object instead.
document.addEventListener('click', (e) => {
  const a = (e.target as Element).closest<HTMLAnchorElement>('[data-goto]');
  if (!a) return;
  e.preventDefault();
  const id = a.dataset.goto as SectionId;
  if (inRoom) {
    const s = SECTIONS.find((x) => x.id === id);
    if (s) openFromRoom(s.object);
    return;
  }
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'start' });
  history.replaceState(null, '', `#${id}`);
  const spot = $('.spotlight', target);
  if (spot) {
    spot.classList.remove('flash');
    setTimeout(() => {
      void spot.offsetWidth; // restart the animation if clicked twice
      spot.classList.add('flash');
    }, reducedMotion() ? 0 : 650);
    spot.addEventListener('animationend', () => spot.classList.remove('flash'), { once: true });
  }
});

for (const b of dockButtons) {
  b.addEventListener('click', () => openFromRoom(b.dataset.object ?? ''));
  const hot = (on: boolean) => room?.highlight(on ? b.dataset.object ?? null : null);
  b.addEventListener('pointerenter', () => hot(true));
  b.addEventListener('pointerleave', () => hot(false));
  b.addEventListener('focus', () => hot(true));
  b.addEventListener('blur', () => hot(false));
}

// Closing the panel zooms the room back out. (The room only draws frames while something
// moves, so it costs nothing to leave it running behind the panel.)
sheetListeners.push((open) => {
  if (!open && inRoom) room?.focus(null);
});

// Pause rendering when the tab is hidden.
document.addEventListener('visibilitychange', () => {
  if (!room || !inRoom) return;
  if (document.hidden) room.pause();
  else room.resume();
});

// Visitor left the site in the room last time: go straight back in, no animation.
if (root.dataset.resumeRoom === '1') enterRoom(undefined, false);
