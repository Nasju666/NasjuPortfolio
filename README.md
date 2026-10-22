# Portfolio: page + room

One portfolio, two ways to see it:

- **Page (default):** a fast, minimal page. Static HTML, about 7 KB of JS, works on any phone.
- **Room:** a semi-realistic 3D desk corner, rendered in Blender with the lighting baked in. Flip the switch and every object on the desk opens a part of the portfolio.

Both modes read from the same content files, and open the same detail panel, so you only ever edit content once.

## Run it

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # outputs static files to dist/
npm run preview   # serve the built dist/ locally
```

Node 22+ recommended.

## Where things live

```
src/content/          <- your content, one Markdown file per entry
  projects/           monitor
  designs/            UI/UX journey (listed under Projects, links straight to Figma)
  work/               laptop (client work, studio roles)
  games/              glowing PC + gamepad (shown as a timeline, oldest first)
  achievements/       trophies on the shelf, and the coach's clipboard on the pull-out tray
  orgs/               corkboard (its photos are pinned on it) + the wall banner
src/data/profile.json name, headline, about, email, links      -> framed print / phone
src/data/skills.json  skill groups                               -> books on the shelf
src/data/sections.ts  section order + which object opens which section
src/data/room.ts      where the room files are
src/content.config.ts the fields each content type accepts
blender/              the scripts that build, render and bake the 3D room
public/models/        the finished room files the website loads
```

### Adding an entry

Copy any existing `.md` file in the same folder and edit it. The part between `---` lines is the short info shown in lists; everything below is the full story in the detail panel (Markdown: lists, links, images).

- `order:` controls sorting (lower first).
- `draft: true` hides an entry without deleting it.
- **Pictures:** put them in `public/images/` (WebP, max ~1600px wide) with a small `name-thumb.webp`
  (192×128) next to each, then list them in the entry's frontmatter:
  ```yaml
  images:
    - src: "kita-1.webp"
      alt: "What the picture shows, for screen readers"
      w: 720     # pixel width and height of the file
      h: 1600
  ```
  The first picture is also the small thumbnail in the list.
- **Trailers:** put the MP4 in `public/videos/` (720p is plenty) and add
  `video: { src: "my-trailer.mp4", poster: "my-cover.webp" }`. It only downloads when someone presses play.
- Originals you sent are kept in `images-assets/`; the site uses the optimised copies.
- Search the project for `TODO` to find every placeholder.

If a field is wrong, `npm run dev` shows an error naming the file and field.

## The room

The room is built entirely by Python scripts that run Blender **without a graphics card**
(Blender's Python module, `bpy`), so it works on any PC, or in the cloud.

```bash
pip install bpy            # Blender as a Python module (Python 3.13 for bpy 5.x)
npm run room:build         # draws screen/poster images, builds blender/room.blend
npm run room:preview       # optional: renders blender/preview.png to check the look
npm run room:bake          # bakes lighting into textures, exports blender/export/room-raw.glb
npm run room:compress      # makes public/models/room.glb and room-low.glb (small, web-ready)
```

`room:bake` at full quality takes a while on a slow CPU (tens of minutes). For a quick look:
`BAKE_SIZE=1024 BAKE_ROOM_SIZE=1024 BAKE_SAMPLES=8 npm run room:bake`
(PowerShell: `$env:BAKE_SIZE=1024; $env:BAKE_ROOM_SIZE=1024; $env:BAKE_SAMPLES=8; npm run room:bake`).

### Changing the room

Everything is in `blender/build_room.py`: positions, sizes, colours, materials, lights and the camera.
Each object is a few lines (look for the comments like `# --- Monitor (Projects)`).

- **Clickable objects** are grouped under empties named `hit_<name>`:
  `hit_monitor`, `hit_laptop`, `hit_pc`, `hit_phone`, `hit_trophies`, `hit_books`, `hit_poster`,
  `hit_corkboard`, `hit_clipboard`, `hit_banner`. `src/data/sections.ts` says which section each one opens
  (`alsoObjects` lets several objects open the same section, like the clipboard → Achievements).
  Everything inside a group lifts and brightens together on hover.
- **`screen_<name>`** objects aren't baked (they glow by themselves). `screen_clock` shows the visitor's live time.
- **`glow_<name>`** objects get a soft halo on the website (the PC fans, the LED strip).
- **Pictures in the room come from your content**, so changing content changes the room (no re-bake):
  the monitor shows the first four Projects with their first picture, the laptop the first Work entry,
  the corkboard the first seven Organizations photos, and the wall banner and framed print the files named
  in `src/data/room.ts` (`ROOM_BANNER`, `ROOM_PRINT`). Under the hood these are `screen_photo_<k>`,
  `screen_banner_photo` and `screen_print_photo` quads laid over plain baked paper; the website blends the
  photo onto the paper so it keeps the room's lighting.
- **Camera:** the website uses the Blender camera exactly (position, lens, lens shift), read from
  `public/models/room-camera.json`. Visitors can only turn it a little, never move it. That's why
  the export can delete faces pointing away from the camera, which halves the triangle count.
- **Close-ups:** opening an object (click, tap or the bottom buttons) turns and zooms the camera onto it,
  framed in the space the panel leaves free; closing the panel glides back. It turns and zooms rather
  than flying, for the same reason: the camera never leaves its spot.

### Swapping in Hyper3D models

Import the GLB in `build_room.py` (`bpy.ops.import_scene.gltf(filepath=...)`), place and scale it
where the simple version was, and delete the simple version. Keep each model under ~5k triangles
(add a Decimate modifier), and parent it to the right `hit_` empty if it should be clickable.

### How the bake works (`blender/bake_export.py`)

1. Applies modifiers, joins the ~180 parts into one mesh per group (baking is much faster that way).
2. Unwraps a second UV map, giving texture space only to faces the camera can see.
3. Bakes all lighting (shadows, bounce light, the blue LED glow on the wall) with Cycles, denoises it,
   and saves it with Blender's AgX look applied, so the browser shows exactly the rendered colours with no lights.
4. Exports the GLB and the camera. `room:compress` then shrinks geometry (meshopt) and textures (WebP).

## Performance notes

- Three.js (~150 KB gzipped) and the room (a few MB) are only downloaded when someone flips the switch.
- The room is drawn unlit (all lighting is baked into textures): no lights, no shadows, ~40k triangles.
- Low-end devices get `room-low.glb` with half-size textures.
- The room renders only when something changes (drag, hover, resize), and stops completely while a panel is open or the tab is hidden, so phones don't heat up or drain battery.
- Quality tiers (`src/scripts/room/quality.ts`): weak devices render at 1× pixels with no antialiasing. Test with `?quality=low` in the URL.
- Visitors with reduced motion turned on get no reveal animation or glide effects.
- No WebGL? The room shows a short message and a button back to the page.

## Deploy

Any static host works; the build output is just files in `dist/`.

- **Vercel / Netlify:** import the GitHub repo, framework "Astro", done.
- **GitHub Pages:** in `astro.config.mjs` set `site: 'https://<user>.github.io'` and, if the repo isn't `<user>.github.io`, `base: '/<repo-name>'`, then use the official `withastro/action` workflow. Note: with a `base`, also update the font path in `global.css` / `Base.astro` (room files pick up `base` automatically).

Set `site` in `astro.config.mjs` to your real URL either way.
