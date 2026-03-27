# MD Viewer — Feature Test

## Text Formatting

**Bold text**, *italic text*, ***bold and italic***, ~~strikethrough~~.

Inline `code` looks like this.

## Headings

### Third Level
#### Fourth Level
##### Fifth Level
###### Sixth Level

## Lists

### Unordered

- First item
    - Nested item A
    - Nested item B
        - Deep nested
- Second item
- Third item

### Ordered

1. Step one
    1. Sub-step A
    2. Sub-step B
2. Step two
3. Step three

### Task List

- [x] Design the UI
- [x] Implement the editor
- [ ] Write documentation
- [ ] Publish to PyPI

## Code Blocks

```python
def fibonacci(n):
    """Return the nth Fibonacci number."""
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

print(fibonacci(10))  # 55
```

```bash
# Install MD Viewer
pip install md-viewer-gtk
mdviewer README.md
```

```javascript
const greet = (name) => `Hello, ${name}!`;
console.log(greet("World"));
```

## Blockquotes

> This is a blockquote.
>
> It can span multiple paragraphs.

> Nested quotes:
> > Inner quote
> > > Even deeper

## Tables

| Feature          | Status | Notes                  |
|:-----------------|:------:|:-----------------------|
| Bold / Italic    | Done   | Standard markdown      |
| Strikethrough    | Done   | Custom extension       |
| Task Lists       | Done   | Custom extension       |
| Code Highlighting| Done   | Via Pygments           |
| Tables           | Done   | With alignment         |

## Links and Images

[Visit Example.com](https://example.com)

![Placeholder Image](https://via.placeholder.com/300x100.png)

## Horizontal Rule

---

## Footnotes

This statement needs a citation[^1].

Another reference here[^note].

[^1]: First footnote with explanation.
[^note]: Named footnotes work too.

## Definition Lists

Markdown
:   A lightweight markup language for creating formatted text.

GTK4
:   The GIMP Toolkit version 4, used for building native Linux applications.

libadwaita
:   A library implementing the GNOME Human Interface Guidelines.

## Abbreviations

*[MD]: Markdown
*[GTK]: GIMP Toolkit
*[HIG]: Human Interface Guidelines

MD Viewer uses GTK4 and follows the GNOME HIG for its user interface design.

## Smart Typography

"Smart quotes" and 'single quotes' --- em dash --- and -- en dash -- and an ellipsis...

## HTML Entities

Copyright &copy; 2026. Temperature: 72&deg;F. Price: &euro;9.99.

## Escaped Characters

\*Not italic\* and \`not code\` and \# not a heading.
