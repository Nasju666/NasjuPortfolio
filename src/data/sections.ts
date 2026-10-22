// One list drives both modes: the order of sections on the minimal page,
// the dock buttons in the room, and which 3D object opens which section.
// `object` must match a hotspot name in the room (placeholder or your GLB: `hit_<object>`).

export type SectionId =
  | 'about'
  | 'projects'
  | 'work'
  | 'games'
  | 'achievements'
  | 'orgs'
  | 'skills'
  | 'contact';

export interface SectionDef {
  id: SectionId;
  title: string; // heading on the page and in the panel
  object: string; // hotspot name in the room (the camera zooms to this one)
  alsoObjects?: string[]; // other room objects that open the same section
}

export const SECTIONS: SectionDef[] = [
  { id: 'about', title: 'About', object: 'poster' },
  { id: 'projects', title: 'Projects', object: 'monitor' },
  { id: 'work', title: 'Work', object: 'laptop' },
  { id: 'games', title: 'Game dev journey', object: 'pc' },
  { id: 'achievements', title: 'Achievements', object: 'trophies', alsoObjects: ['clipboard'] },
  { id: 'orgs', title: 'Organizations', object: 'corkboard', alsoObjects: ['banner'] },
  { id: 'skills', title: 'Skills', object: 'books' },
  { id: 'contact', title: 'Contact', object: 'phone' },
];

export const sectionByObject = (object: string) =>
  SECTIONS.find((s) => s.object === object || s.alsoObjects?.includes(object));
