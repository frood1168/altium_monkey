# SchLib

`AltiumSchLib` is the public container for schematic libraries. Each library
contains one or more `AltiumSymbol` objects.

Use it when you need to:

1. create schematic symbols
2. mutate existing symbols
3. split or merge schematic libraries
4. extract symbols from schematic documents
5. render symbols and multipart symbols to SVG

## Object Model

`AltiumSymbol` uses the same `ObjectCollection` pattern as `AltiumSchDoc`.
Symbol properties such as `symbol.pins`, `symbol.parameters`,
`symbol.rectangles`, `symbol.lines`, and `symbol.arcs` are typed query views.

Add symbol records with `symbol.add_object(...)` or symbol helper methods. Keep
visual ordering in mind: body graphics should usually be behind pins and text.
That order is preserved when a symbol is inserted into a SchDoc through
`AltiumSchDoc.add_component_from_library(...)` and when placed symbols are
extracted back to SchLib.

## Units

Public SchLib authoring APIs use mils for geometry. Use public helpers and
enums for pins, fonts, and drawing styles. Avoid raw pin binary fields unless
you are doing serializer-level preservation work.

## Public Pattern

Create or load a library, add or find a symbol, mutate the symbol, then save:

```python
schlib = AltiumSchLib()
symbol = schlib.add_symbol("MY_SYMBOL")
symbol.add_object(make_sch_pin(...))
schlib.save("my_symbols.SchLib")
```

Pass `show_comments_designators=True` when creating a library if Altium should
open the SchLib editor with symbol comments and designators visible:

```python
schlib = AltiumSchLib(show_comments_designators=True)
```

You can also set `schlib.show_comments_designators = True` before saving.

For parsed libraries, prefer `AltiumSchLib.get_symbol(...)` and symbol views
over scanning raw streams.

## SVG Rendering

`AltiumSchLib.symbol_to_svg(...)` and `to_svg(...)` accept
`SchSvgRenderOptions`. Normal symbol SVG output includes a root `viewBox` in
schematic pixel-canvas coordinates. Pass
`SchSvgRenderOptions(include_view_box=False)` to omit only that root attribute
while keeping the same geometry and symbol rendering path.

## Examples

Start with:

1. [`hello_schlib`](../examples/hello_schlib/README.md)
2. [`schlib_find_symbol`](../examples/schlib_find_symbol/README.md)
3. [`schlib_split`](../examples/schlib_split/README.md)
4. [`schlib_merge`](../examples/schlib_merge/README.md)
5. [`schlib_svg`](../examples/schlib_svg/README.md)
6. [`schdoc_extract_schlib`](../examples/schdoc_extract_schlib/README.md)

See [API patterns](api_patterns/index.md) for the shared `ObjectCollection`
rules used by SchDoc and SchLib.

