# Public Docs Style Foundation

The public documentation is Markdown-first in this release. The checked-in
stylesheet at [assets/altium-monkey-docs.css](assets/altium-monkey-docs.css)
is the shared visual foundation for current static docs and future generated
HTML docs.

The visual source of truth is the Monkey Kit `altium_monkey` golden bundle.
The public docs copy uses the amber phosphor theme, the Altium Monkey ASCII
mark, and the generated Altium Stroke font assets.

## Scope

The stylesheet is intentionally dependency-free:

1. No static-site generator is required.
2. Markdown files remain readable without CSS.
3. Generated docs can reuse the same CSS variables and utility classes.
4. The generated webfont files are static assets, not runtime dependencies.

## Design Tokens

The stylesheet exposes stable Monkey Kit `--mk-*` variables for:

1. background, panel, input, border, accent, text, and diagnostic colors
2. mono and sans font stacks
3. spacing, radius, glow, and transition values

Future generated docs should consume these variables instead of hard-coding a
separate palette.

The public docs stylesheet also defines `--am-font-stroke` as a compatibility
token for consumers that want the generated Altium schematic stroke font
without coupling to Monkey Kit token names.

## Font Assets

The upstream stroke-font generator produced:

1. [assets/fonts/altium-stroke.woff2](assets/fonts/altium-stroke.woff2)
2. [assets/fonts/altium-stroke.woff](assets/fonts/altium-stroke.woff)
3. [assets/fonts/altium-stroke.ttf](assets/fonts/altium-stroke.ttf)
4. [assets/fonts/altium-stroke.otf](assets/fonts/altium-stroke.otf)
5. [assets/fonts/altium-monkey-stroke-fonts.css](assets/fonts/altium-monkey-stroke-fonts.css)

`assets/altium-monkey-docs.css` embeds the same `@font-face`, using
`font-family: "Altium Stroke"`. Use this face for Altium-style schematic text
samples or generated design-document diagrams. Do not force it onto monospace
code blocks or the ASCII monkey mark.

## Monkey Mark

The Altium Monkey mark is published as:

1. [assets/monkey/altium-monkey.html](assets/monkey/altium-monkey.html)
2. [assets/monkey/altium-monkey.txt](assets/monkey/altium-monkey.txt)
3. [assets/monkey/altium-monkey-preview.png](assets/monkey/altium-monkey-preview.png)

Generated HTML docs can embed the HTML fragment when a branded status/header
mark is useful. The fragment assumes `assets/altium-monkey-docs.css` or the
portable Monkey Kit CSS has already been loaded.

## Generated Docs Guidance

Generated pages should wrap body content in either a semantic `main` element or
an `.am-doc` container. Optional callouts can use `.am-callout`, and compact
section labels can use `.am-kicker`.

Generated pages that want the full Monkey Kit document treatment should set
`data-theme="amber"` on the root element and load:

```html
<link rel="stylesheet" href="assets/altium-monkey-docs.css">
```
