---
name: Alpine Operational Minimalist
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3f4850'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#6f7881'
  outline-variant: '#bfc7d1'
  surface-tint: '#006495'
  primary: '#006495'
  on-primary: '#ffffff'
  primary-container: '#4aa9e9'
  on-primary-container: '#003b5b'
  inverse-primary: '#8fcdff'
  secondary: '#545f73'
  on-secondary: '#ffffff'
  secondary-container: '#d5e0f8'
  on-secondary-container: '#586377'
  tertiary: '#006591'
  on-tertiary: '#ffffff'
  tertiary-container: '#21abef'
  on-tertiary-container: '#003c58'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cbe6ff'
  primary-fixed-dim: '#8fcdff'
  on-primary-fixed: '#001e30'
  on-primary-fixed-variant: '#004b71'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#c9e6ff'
  tertiary-fixed-dim: '#89ceff'
  on-tertiary-fixed: '#001e2f'
  on-tertiary-fixed-variant: '#004c6e'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-lg:
    fontFamily: Lexend
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Lexend
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-sm:
    fontFamily: Lexend
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Lexend
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Lexend
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: Lexend
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-lg:
    fontFamily: Lexend
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1'
  label-md:
    fontFamily: Lexend
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
  label-sm:
    fontFamily: Lexend
    fontSize: 10px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin: 32px
---

## Brand & Style

This design system is engineered for the high-stakes environment of winter sports management. The brand personality is rooted in clarity, efficiency, and reliability. It avoids unnecessary ornamentation to ensure that operational data—such as lift statuses, weather alerts, and staff scheduling—remains the central focus.

The visual style follows a **Corporate Modern** approach with a heavy emphasis on **Minimalism**. By utilizing a high-contrast ratio between the primary brand color and a pure white background, the interface evokes the crisp, invigorating feeling of a fresh snowpack. It prioritizes functional aesthetics to build trust with users who require precision and speed in their daily workflows.

## Colors

The palette is anchored by a vibrant sky blue derived from the brand’s core identity, signifying optimism and the open outdoors. 

- **Primary Blue:** Used for call-to-actions, active states, and primary navigational elements.
- **Secondary Slate:** A deep, cool-toned dark grey used for primary text and iconography to ensure high legibility against white.
- **Surface Neutrals:** A range of cool greys is used for borders and secondary text, maintaining a cohesive "alpine" temperature throughout the interface.
- **Pure White:** The absolute background color ensures maximum contrast and a clean, sterile environment that prevents visual fatigue.

## Typography

Lexend was selected for its exceptional readability and "hyper-sans" characteristics, designed specifically to reduce visual stress. Its expanded letterforms and generous inner-spacings make it ideal for quick scanning on mobile devices in bright outdoor light or glare.

The hierarchy is structured to be "headline-heavy," using bold weights to clearly demarcate sections of data. Labels use a slightly increased tracking (letter spacing) in smaller sizes to maintain legibility when used in dense data tables or status indicators.

## Layout & Spacing

The layout utilizes a **12-column fluid grid** for desktop dashboards, transitioning to a single-column stack for mobile devices. A strict 8px base unit (the "Step") governs all spatial relationships.

Vertical rhythm is maintained by using the `md` (24px) spacing for most component-to-component gaps, while `lg` (40px) is reserved for separating major content sections. Padding within containers should always be consistent to reinforce the professional, organized feel of the application.

## Elevation & Depth

This design system avoids heavy drop shadows to maintain a flat, modern aesthetic that doesn't feel cluttered. Depth is communicated through:

- **Low-contrast Outlines:** Elements like cards and inputs use a 1px border in a light grey (`#E2E8F0`).
- **Tonal Layers:** Secondary containers or background sections use a very light blue-grey tint to distinguish them from the pure white primary surface.
- **Focus States:** High-visibility 2px primary blue outlines are used for active keyboard focus, ensuring the app is accessible and navigable in all conditions.
- **Subtle Ambient Shadows:** Only used for floating elements like modals or dropdown menus, employing a very soft, diffused blur with low opacity (10%) to suggest they sit directly above the surface.

## Shapes

The shape language is defined by a consistent **8px (0.5rem)** corner radius. This "Rounded" approach strikes a balance between the clinical feel of sharp corners and the overly casual nature of pill-shaped buttons.

This specific radius is applied to:
- Buttons and action items.
- Form inputs and text areas.
- Data cards and info containers.
- Modal windows and popovers.

Iconography should follow this rounded logic, avoiding sharp terminal points in favor of slightly softened ends.

## Components

### Buttons
Primary buttons use the full sky blue fill with white text for maximum prominence. Secondary buttons use a sky blue border with sky blue text. All buttons have a height of 40px or 48px to remain touch-friendly for users who might be wearing thin liners or gloves.

### Input Fields
Inputs are defined by a 1px light grey border and 8px rounded corners. On focus, the border transitions to the primary sky blue with a subtle glow. Labels are always positioned above the field in `label-lg` for clarity.

### Cards
Cards are the primary container for resort data. They feature a white background, the standard 8px radius, and a subtle 1px border. No shadows should be used on standard cards to keep the dashboard feeling light and airy.

### Status Chips
Critical for a management app, these small badges use the `label-sm` typography. They utilize light tinted backgrounds (e.g., light green for 'Open', light red for 'Closed') with high-contrast text to provide at-a-glance status updates.

### Data Lists
Lists utilize thin horizontal dividers rather than boxes to save space. Each row should have a minimum height of 56px to ensure ease of interaction.