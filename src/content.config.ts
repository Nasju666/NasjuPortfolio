// Content schema. Every entry is one Markdown file in src/content/<collection>/.
// The frontmatter (between the --- lines) is the short info shown in lists;
// the Markdown body below it is the full story shown in the detail panel.
import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const link = z.object({ label: z.string(), url: z.string() });

// Pictures and trailers live in public/images and public/videos.
// `src` is the file name inside that folder; w/h are the image's pixel size (stops the page jumping).
const image = z.object({ src: z.string(), alt: z.string(), w: z.number(), h: z.number() });
const media = {
  images: z.array(image).default([]), // first image is also the list thumbnail
  video: z.object({ src: z.string(), poster: z.string().optional() }).optional(),
};

const base = {
  order: z.number().default(99), // lower = shown first
  draft: z.boolean().default(false), // true = hidden from the site
};

const projects = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/projects' }),
  schema: z.object({
    ...base,
    ...media,
    title: z.string(),
    summary: z.string(),
    role: z.string().optional(),
    period: z.string().optional(), // e.g. "2025" or "2024 – present"
    context: z.string().optional(), // e.g. "Sinulog PropTech Hackathon", "School project"
    tech: z.array(z.string()).default([]),
    links: z.array(link).default([]),
    featured: z.boolean().default(false),
  }),
});

// UI/UX journey, shown under Projects as a timeline.
const designs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/designs' }),
  schema: z.object({
    ...base,
    ...media,
    title: z.string(),
    year: z.string(),
    note: z.string().optional(), // e.g. "My first Figma design"
    links: z.array(link).default([]),
  }),
});

const work = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/work' }),
  schema: z.object({
    ...base,
    ...media,
    title: z.string(), // app / product name
    client: z.string().optional(),
    summary: z.string(),
    role: z.string(),
    period: z.string().optional(),
    status: z.string().optional(), // e.g. "Maintaining"
    tech: z.array(z.string()).default([]),
    links: z.array(link).default([]),
  }),
});

// Game dev journey: shown as a timeline in `order`.
const games = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/games' }),
  schema: z.object({
    ...base,
    ...media,
    title: z.string(),
    summary: z.string(),
    when: z.string().optional(), // label on the timeline, e.g. "2025" or "First game"
    spotlight: z.boolean().default(false), // the newest game: big card at the top of the section + link in the intro
    badge: z.string().optional(), // small tag on the timeline, e.g. "New"
    platform: z.string().optional(), // e.g. "Roblox"
    role: z.string().optional(),
    status: z.string().optional(),
    links: z.array(link).default([]),
  }),
});

const achievements = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/achievements' }),
  schema: z.object({
    ...base,
    ...media,
    title: z.string(), // the result, e.g. "Grand finalist"
    event: z.string(),
    when: z.string(),
    team: z.string().optional(),
    project: z.string().optional(), // what you built for it
    role: z.string().optional(), // e.g. "Coach" when you led the team rather than competed
    featured: z.boolean().default(false), // featured ones get a trophy in the room
    links: z.array(link).default([]),
  }),
});

const orgs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/orgs' }),
  schema: z.object({
    ...base,
    ...media,
    org: z.string(),
    position: z.string(),
    period: z.string(),
    current: z.boolean().default(false),
  }),
});

export const collections = { projects, designs, work, games, achievements, orgs };
