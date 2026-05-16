# JSON Glance

*See the shape of any JSON or nested data at a glance.*

[![PyPI](https://img.shields.io/pypi/v/json-glance)](https://pypi.org/project/json-glance/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)

**`df.describe()` for JSON and nested data.** One call shows the *shape* of any
nested data - types, nesting, sizes, ranges, null rates - instead of scrolling
through raw JSON.

Zero dependencies. Pure standard library. Python 3.9+.

```bash
$ json-glance examples/api_response.json
dict  · 4 keys
├─ products  list  · 3 items
│  └─ dict  · 7 keys
│     ├─ id          str    len 36  ~uuid
│     ├─ name        str    len 9 – 13
│     ├─ price       float  89.5 – 1395
│     ├─ in_stock    bool   67% true
│     ├─ tags        list   · 1 – 2 items
│     │  └─ str  len 6 – 9
│     ├─ dimensions  dict   · 3 keys
│     │  ├─ width   int  8 – 60
│     │  ├─ depth   int  8 – 30
│     │  └─ height  int  18 – 48
│     └─ discount    float  = 0.15  (67% missing)
├─ count     int   = 3
├─ currency  str   len 3
└─ cursor    null
```

Three product records merged into one shape: `id` always looks like a UUID,
`discount` is set on only one of the three, `cursor` is always null.

## Install

```bash
pip install json-glance
```

## Library

```python
from json_glance import glance, summary

glance(data)            # print the summary
text = summary(data)    # ...or get it as a string
glance(data, depth=3)   # limit how deep it descends
```

## CLI

```bash
json-glance response.json     # summarize a JSON file
json-glance events.jsonl      # newline-delimited JSON - all records merged
curl -s https://api.example.com/x | json-glance   # straight from a pipe
```

## It catches data bugs

```bash
$ json-glance examples/messy.json
list  · 5 items
└─ dict  · 5 keys
   ├─ sku       str                len 6
   ├─ price     float | int | str  (20% int, 20% str)
   ├─ qty       int | null         (20% null)
   ├─ on_sale   bool               60% true
   └─ discount  float              0.1 – 0.2  (60% missing)
```

That `price` line caught a bug: across five records, one `price` is a string
(`"call for quote"`) and one is an `int` where the rest are floats - something
you would not spot scrolling raw JSON.

## What it shows

- **Merged shapes** - a list of 10,000 dicts becomes one schema, not 10,000 lines.
- **Honest denominators** - `(67% missing)` means the key was absent; `(20% null)`
  means the value was `None`. Tracked separately, never conflated.
- **Type unions** - mixed types shown as `int | str | null` with each share.
- **Value stats** - numeric ranges, string-length ranges, boolean true-rates.
- **Pattern hints** - `~email`, `~uuid`, `~datetime`, shown only when *every*
  value at that position matches. `~` means hint, not guarantee.
- **Map detection** - a dict used as a key-value store is summarized as a map,
  not dumped as a giant record.
- **Safe** - never recurses into `__dict__`, never calls your code; non-JSON
  values are reported by type name. Self-referential structures render `<cycle>`.

## API

| Function | Returns | |
|---|---|---|
| `glance(data, *, depth=6, max_keys=50, file=None)` | `None` | prints the summary |
| `summary(data, *, depth=6, max_keys=50)` | `str` | returns the summary |

- `depth` - nesting levels to show before collapsing to `…`.
- `max_keys` - record keys to show before `+N more`.

## License

MIT.
