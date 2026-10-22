// Room files, produced by the Blender pipeline in /blender (see README).
//   room.glb         full quality (2048px baked textures)
//   room-low.glb     same room with 1024px textures, used on low-end devices
//   room-camera.json the Blender camera (position, direction, lens, shift)
//
// Clickable objects in the GLB are named `hit_<object>`; src/data/sections.ts maps them to sections.
const base = import.meta.env.BASE_URL.replace(/\/$/, '');
export const MODEL_URL = `${base}/models/room.glb`;
export const MODEL_URL_LOW = `${base}/models/room-low.glb`;
export const CAMERA_URL = `${base}/models/room-camera.json`;

// Pictures in the room that don't come from a single content entry (files in public/images/).
//   ROOM_BANNER  hangs on the wall above the shelf (wide image, about 2.7 : 1)
//   ROOM_PRINT   the framed print on the shelf
// The corkboard shows the Organizations photos (first seven, the banner skipped),
// the monitor the first four Projects, the laptop the first Work entry.
export const ROOM_BANNER = 'sbg-banner.webp';
export const ROOM_PRINT = 'nasju-500.webp';
