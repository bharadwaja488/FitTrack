# FitTrack Design System

FitTrack uses a premium dark visual system across public pages and authenticated fitness tools. The redesign keeps the existing React components, Flask APIs, session authentication, database and console app intact.

## Colors

| Role | Token | Value |
| --- | --- | --- |
| Main background | `--bg` | `#0B0F14` |
| Sidebar | `--sidebar` | `#10161D` |
| Primary card | `--panel` | `#151D26` |
| Secondary surface | `--panel2` | `#1B2530` |
| Emerald action | `--emerald` | `#10B981` |
| Positive highlight | `--emerald-bright` | `#34D399` |
| Primary text | `--text` | `#F8FAFC` |
| Secondary text | `--muted` | `#94A3B8` |
| Muted text | `--muted2` | `#64748B` |
| Border | `--line` | `#263442` |
| Warning | `--warning` | `#F59E0B` |
| Error | `--error` | `#EF4444` |

Use emerald for primary actions, active navigation, positive trends and progress. Reserve warning and error colors for their semantic states. Charts use emerald as their main series color and continue to render only API-backed records.

## Typography

Use Inter with system sans-serif fallbacks. Page titles use a compact, bold hierarchy; card headings use medium weight; body text remains at least 12–14 px in the main application. Small uppercase labels are reserved for metric captions and section eyebrows.

## Spacing, borders and shadows

- Card radius: 16 px (`--radius-card`)
- Control radius: 10 px (`--radius-control`)
- Standard card gaps: 14–16 px
- Main desktop content padding: 38 px, reduced at tablet and mobile widths
- Borders use `#263442` with stronger `#344354` outlines for controls
- Cards use a soft, low contrast shadow (`--shadow-card`); avoid glow effects

## Components

Reuse the existing `.panel`, `.stat-card`, `.button`, `.form-stack`, `.filter-bar`, `.empty-state`, `.loading-panel`, `.form-error`, `.chart` and `.nav-item` patterns. Primary buttons use emerald; secondary actions use a bordered dark surface; destructive actions use red. Inputs and selects share a dark fill, visible border, focus ring and readable placeholder color. Keep empty, loading and error states distinct.

## Responsive behavior

- Desktop: fixed 252 px sidebar and padded content area
- Tablet: sidebar narrows and card grids reduce columns
- Mobile (760 px and below): sidebar becomes an off-canvas drawer, page grids stack and content padding contracts
- Small mobile (440 px and below): metric cards, filter controls and form rows stack to avoid horizontal overflow
- Charts remain fluid within their card and tables retain a bounded horizontal scroll container

## Motion and accessibility

Use existing Framer Motion entrances sparingly. The root `MotionConfig` honors the user's reduced-motion preference; CSS transitions and animations are also minimized when `prefers-reduced-motion: reduce` is active. Keep keyboard focus visible and use emerald focus rings with sufficient contrast.

## Product constraints

The UI must not fabricate profile metrics, activity, calorie estimates, goals or weight progress. Exercise calories remain manually recorded. Nutrition remains removed from the application interface and APIs; its historical migration files and stored records are preserved.
