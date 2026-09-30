---
name: ffwai-ui-theme
description: Enforces the "California Ember" 60-30-10 UI/UX theme and color palette for the FightFireWithAI frontend.
---

# FightFireWithAI UI/UX Theme (California Ember)

When generating, refactoring, or styling frontend components (React/Tailwind CSS) for the FightFireWithAI application, you MUST strictly adhere to the "California Ember" theme. 

This application uses the **60-30-10 color rule** to balance professional readability with emergency-ready aesthetics suitable for a wildfire prediction tool.

## The 60-30-10 Palette

### 1. 60% Base (Backgrounds & Structure)
- **Tailwind Classes:** `bg-slate-50`, `bg-white`
- **Usage:** Use for all primary backgrounds, side-drawers, cards, and large structural elements. The map itself acts as a light base (`outdoors-v12`), so UI components should blend cleanly using Off-White or Pure White.

### 2. 30% Secondary (Typography & Borders)
- **Tailwind Classes:** `text-slate-800`, `border-slate-200`, `text-slate-900`
- **Usage:** Use Dark Slate (`text-slate-800`) for all standard text, headers, paragraphs, and labels to ensure maximum high-contrast readability against the light base. Use lighter slate (`border-slate-200`) for subtle structural borders and dividers. 
- **Avoid:** Do not use `text-slate-500` or `text-gray-500` for primary readable text, as it violates contrast requirements.

### 3. 10% Accent (Interactive & Alerts)
- **Tailwind Classes:** `bg-orange-600`, `text-orange-600`, `border-orange-600`
- **Usage:** Use the "Burnt Crisp Orange" accent *sparingly* but deliberately. It should only be used for:
  - Active states on toggle switches (e.g., `bg-orange-600`)
  - Primary call-to-action buttons
  - Brand identity elements (e.g., the "WithAI" in the logo)
  - Critical alerts or highlights

## Best Practices
- **Minimalism:** Do not clutter the map. Use floating pills and collapsible side-drawers or dropdowns instead of massive permanent floating cards.
- **Flush Components:** Components like timeline scrubbers should be docked perfectly flush to the edges of the screen to preserve "zero central map space".
- **Responsive:** Ensure fixed widths are paired with max-widths (e.g., `w-full max-w-[400px]`) so drawers don't bleed off-screen on mobile devices.

